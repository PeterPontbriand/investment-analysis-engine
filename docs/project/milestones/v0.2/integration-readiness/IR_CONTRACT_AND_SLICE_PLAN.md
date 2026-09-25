# IR — Integration Readiness Contract and Slice Plan

Defines scope, sequencing, and acceptance for making the four existing analyses safely
consumable by an external harness (backtester, optimizer, or other automated consumer),
without turning this project into that harness.

Local sequence and status: this document. Cross-package placement is in the
[milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status). A later, separately drafted
[candidate backlog](../../../EVIDENCE_PROVIDER_ROADMAP.md) drew on the same originating review and
surfaced overlapping "library-readiness" observations, not an independent conclusion; where its
scope duplicated this document's, this document remains the authoritative source and the backlog
defers to it.

## 1. Origin and framing

A separate review (an independent assessment of this project's suitability for integration with
an external genetic-algorithm backtester, conducted 2026-09, project owner's own initiative)
concluded that integrating with that particular external project was not viable — for reasons
unrelated to this project's own quality, primarily a domain mismatch between fundamentals-driven
periodic screens and a bar-by-bar trading system. The project owner agreed with that conclusion.
That review nonetheless surfaced genuine, verifiable shortcomings in this project's own
integration surface, independent of any specific external consumer. Every specific claim in that
review was independently re-verified against the current codebase before this plan was drafted;
none were taken on faith, and the scope below reflects that verification, not the original
review's wording.

**Framing, per the project owner's explicit agreement:** this project's natural role for an
external consumer is as a point-in-time evidence and filter provider — "only allow a signal in
an equity where Graham passes and Momentum is bullish as of date T" — not as a trading-signal or
order-generation system. This matches the project's own existing design intent: Graham Number is
explicitly a screening ceiling, Graham Growth an explicit forecast-dependent estimate, and
Momentum a regime label, none of them an entry/exit rule. This work package makes that existing
role more safely consumable; it does not add trading logic, backtesting infrastructure, or a new
strategy shape.

## 2. Scope

In scope, each independently landable:

1. **License declaration fix.** `LICENSE` is Apache-2.0; `pyproject.toml` declares
   `license = {text = "MIT"}`. **Decided, with explicit project-owner authorization (2026-09-23):
   standardize on Apache-2.0** — `pyproject.toml`'s declaration changes to match `LICENSE`, not
   the reverse. Choosing between the two was a licensing decision requiring the project owner's
   sign-off, not an engineering judgment call; that sign-off is recorded here. The actual
   `pyproject.toml` edit is a code/config change and happens when IR.1 is implemented, not as part
   of any docs-only pass.
2. **`MOMENTUM.md` self-contradiction — already corrected.** Line 44 documented the simple-average
   RSI convention while line 118 listed RSI among indicators "not currently implemented." Fixed
   directly (a user-facing documentation correction, not a planning change) rather than waiting
   for IR.1's implementation slice, since the actual and correctly-documented behavior in
   `FINANCE_MATH.md` and `GLOSSARY.md` was never in question. IR.1 accordingly now consists only of
   the license fix.
2a. **Found and fixed as part of IR.1: `pyproject.toml` declares `requires-python = ">=3.12"`, but
    `src/analysis/strategy/momentum/momentum_analyzer.py:268`'s `_calculate_rsi(close: pd.Series[float], ...)`
    annotation is evaluated eagerly at import time on Python 3.12/3.13 (traditional CPython
    behavior) — `pd.Series` does not support `__getitem__`, so `import momentum_analyzer` raises
    `TypeError: type 'Series' is not subscriptable` immediately on either declared-supported
    version. This was invisible in this environment only because Python 3.14 (PEP 649) defers
    annotation evaluation by default, masking the failure; verified directly by reproducing the
    `TypeError` from a bare `pd.Series[float]` expression and by confirming a function with an
    undefined annotation name defines without error on 3.14 until `__annotations__` is actually
    accessed. **Decided: fix the annotation, not the Python floor.** Every other file under
    `src/analysis/strategy/*/*.py` already opens with `from __future__ import annotations`
    (`momentum_analyzer.py` was the sole exception); adding it there is the minimal, standard,
    already-precedented fix — annotations become lazy strings on every supported Python version
    (3.12, 3.13, 3.14 alike) via the same mechanism, rather than the module only working by
    accident on 3.14 through an unrelated language default. Raising `requires-python` to `>=3.14`
    was rejected as disproportionate: it would cut off 3.12/3.13 entirely for what is a one-line,
    fully backward-compatible fix, and 3.14 is new enough that narrowing to it is not otherwise
    warranted. Full suite re-run after the fix: 3142 passed (up from 3129 — the 13 new §6.6
    conformance tests), `mypy --strict` clean.
3. **Unify the analyzer invocation envelope.** Per `AGENTS.md` §9 (added 2026-09-24) and §0's
   temporary consolidation-period authorization: every strategy subclasses
   `BaseAnalyzer[ConfigT, ResultT]` and is invoked as `run_analysis(ticker, config, context)`,
   where `ticker: str` is always required, `config: ConfigT` is the strategy's own typed
   user-selectable configuration, and `context: AnalysisContext` is one frozen dataclass carrying
   the four cross-cutting concerns every strategy shares — `as_of`, `executed_at`, `use_cache`,
   `instrument_profile` — each with **one meaning read by all four analyzers, with no exceptions**
   (revised 2026-09-24: an earlier draft of this plan let Graham skip a shared clock field; that
   exception is now closed — see §6). **Revised 2026-09-25, found and fixed during IR.2.1
   implementation (§6.1 item 12):** an earlier draft of this plan gave `AnalysisContext` a single
   `effective_as_of` field and called it "the one clock any analysis-layer code reads." That
   collapses two genuinely different concerns into one value: for a historical run (`as_of` set),
   the requested cutoff and the run's actual execution time diverge, and no single field can
   correctly answer both "what point in time should data be truncated to" and "when did this run
   actually execute, for freshness/TTL/timestamp purposes." `AnalysisContext` instead carries
   `executed_at` — a single timezone-aware read of "now," taken once per run, the sole clock for
   freshness/TTL/result-timestamp concerns — and derives `effective_as_of` as a read-only property
   (`as_of or executed_at`), the point-in-time cutoff for data truncation/availability concerns.
   `use_cache` is the single control for whether a run's cache is read or written, for all four, with the durable cache
   itself always wired at composition but opening storage lazily, on first actual read or write, not
   at composition time (no more build-time enabled/disabled cache choice, and no regression on a
   machine where storage is missing or fails Step 3.3A's readiness checks — see §6.1 item 10).
   `BaseAnalyzer` has no `__init__`, no `default_ticker`, and no `config_schema`; every analyzer
   receives its dependencies (resolvers, data clients, calculation policies) at construction,
   injected and required — no analyzer constructs its own client, reads `src.config.settings`
   directly, or calls `datetime.now`/an uninjected clock, and this rule now extends to the shared
   resolver infrastructure Graham's and FCF's analyzers depend on, not only the analyzer classes
   themselves (§6). `FCFEarningsGrowthAnalyzer` and `GrahamNumberAnalyzer`/`GrahamGrowthAnalyzer`
   (the latter two already analyzer-mediated on the workspace path but bypassed by the orchestrator,
   which calls their service functions directly) all become genuinely single-entry-point per
   strategy, through one shared selection-to-`(config, context)` mapping used by every composition
   root for a given strategy, not independently re-derived per call site. This is a consolidation,
   not merely a typing correction: per `AGENTS.md` §0, persisted evidence/config shapes may change
   (version fields bump; no migration or compatibility code) and public constructors/signatures may
   change where the envelope requires it. It does not create a generic result supertype, registry,
   or factory — each strategy's `ConfigT`/`ResultT` remain its own types, per `AGENTS.md` §9.
   Full inventory, field-placement decisions, call-site enumeration, and the slice list this scope
   is delivered through: §6.
   No formula, classification, or calculation result changes; a calculation believed incorrect is
   reported, not fixed, here.
4. **Momentum reaches full parity with the other three strategies — decided now, folded into IR.2,
   IR.3 no longer exists as a separate slice.** Everything IR.3 previously scoped is now part of
   IR.2's slice list (§6), since achieving "one meaning per context field, all four analyzers" is
   inseparable from Momentum's own reshaping:
   - **Quality-check/clock purity.** `MomentumAnalyzer.run_analysis` (today) calls `datetime.now(UTC)`
     twice, uninjectable, and its internal quality re-check ignores `as_of` and duplicates the check
     `MomentumInputResolver.resolve()` already performed. **Decided:** the resolver checks and
     publishes quality once, exactly as today; `run_analysis` performs its own independent,
     `as_of`-aware re-check using `context.executed_at` as its clock (defense in depth; per §6.11's
     corrected rule, `effective_as_of` is never wired as a clock — the resolver's own truncation to
     `as_of` already happened before this re-check runs) but does
     **not** publish. The frame-based calculation is extracted into a pure module-level function,
     `compute_momentum_metrics(df, config, ticker, timestamp) -> MomentumMetrics`, with no quality
     check, telemetry, clock read, or logger of its own. Closes the point-in-time-integrity gap
     under Core Design Principle #10 (`MASTER_PLAN.md` §3), not only a testability one.
   - **`MomentumPolicy` is deleted, not lazily fixed.** Investigated per the project owner's
     direction: `MomentumPolicy` (`momentum_analyzer.py:87-100`) duplicates `MomentumConfig`'s three
     fields and validation exactly, except using the eager `short_window: int = _get_default_short_window()`
     pattern instead of `MomentumConfig`'s existing correct `Field(default_factory=...)` one. Its
     only production use is `orchestrator/analysis_tools.py:69`'s `_MOMENTUM_DEFAULTS = MomentumPolicy()`,
     sourcing `MomentumToolArguments`' field defaults — `MomentumConfig` already supplies the exact
     same values the exact same way. **Finding: delete `MomentumPolicy` entirely and source those
     defaults from `MomentumConfig` instead**, rather than lazily fixing a class that turns out to be
     a pure duplicate. One test (`test_momentum_hardening.py:13,61`) constructs `MomentumPolicy`
     directly and switches to `MomentumConfig`.
   - **Real `as_of`/`use_cache`, not placeholder fields.** Corrected 2026-09-24: `MomentumToolArguments`
     already inherits `as_of: datetime | None = None` from the shared `_AnalysisToolArguments` base
     (`analysis_tools.py:49`), and `analyze_momentum` already passes it through to
     `run_with_context` (`analysis_tools.py:179-183`) — the orchestrator path already wires `as_of`
     end-to-end today; only the CLI and the persisted `MomentumSelection` were missing it.
     `MomentumToolArguments` therefore gains only `use_cache: bool = True` (matching the other three
     tool-argument models exactly), not `as_of`. Momentum gains genuine `--as-of` and `--no-cache`
     CLI options (matching the other three exactly) and `MomentumSelection.as_of`/`use_cache` fields
     wired to them — not inert schema placeholders. `MomentumInputResolver.resolve` already
     truncates historical prices to `as_of` correctly (verified, not changed); `MOMENTUM.md` gains a
     note that provider-adjusted historical prices are revised retroactively, so an `as_of` result is
     not strictly point-in-time evidence of what was knowable on that date. Full cache-threading plan
     and `as_of`/CLI wiring: §6.
   - **Instrument profile, injected dependencies, ticker default.** `instrument_profile` is unified
     (§6.4); `MomentumAnalyzer.__init__` loses its `YFinanceClient()` default and its `settings`
     reads (moved to composition roots); its TOML ticker-default fallback moves to the CLI, and
     Graham's already-dead `_resolve_ticker` fallback is deleted outright.
5. **Momentum series API.** `run_analysis` already computes full rolling SMA series
   (`close_series.rolling(window=s_win).mean()`) and then discards everything except
   `.iloc[-1]`. Expose a pure, vectorized function returning the full computed series (SMA
   short/long, RSI, crossover) beneath the existing snapshot-returning public API, so a caller
   evaluating many points in one series does not pay one full fetch-and-recompute per point.
   Scoped to Momentum only — Graham Number, Graham Growth, and FCF/Earnings Growth evaluate once
   per fiscal period, not once per bar, and a per-bar series API would be speculative generality
   for those three, not a real need. Renumbered from IR.4 to IR.3 now that the slice between it and
   IR.2 (previously IR.3, Momentum purity) no longer exists as a separate slice — see §3.
6. **Removed from this work package's scope 2026-09-24, moved to SWC.** Typed JSON envelope models
   and generated JSON Schemas for `--json` payloads (previously item 7 / slice IR.5) are per-strategy
   wiring in the same shape as everything else `SWC`'s proposal (`../STRATEGY_WIRING_CONSOLIDATION_PROPOSAL.md`)
   catalogs: one hand-written builder per strategy today, about to become five more with Step 3.5.
   Building it on `SWC`'s shared strategy descriptor means writing it once, not four (soon nine)
   times by hand. The substance of the original scoping — real typed envelope models backing the
   payload builders, not a snapshot generated once from whatever happens to exist, published to a
   checked-in `schemas/` directory — carries forward unchanged into `SWC`'s own eventual contract;
   only the work package that owns it changed.

Excluded: any new trading-signal, entry/exit, or order-generation capability; a
`compute_series`-style API for the three fundamentals-based analyses; an actual MCP server,
subprocess boundary, or harness adapter (this work package makes that future possible, it does
not build it); backtester-specific integration code for any named external project; changing any
analysis's existing formulas, classifications, or presentation contracts beyond what's needed to
fix the specific defects above; the `src` → real package rename, moved out to its own work
package (`PKG`, see `IMPLEMENTATION_PLAN.md`'s sequencing table) given its scale relative to
everything else here.

## 3. Sequencing

Each slice ends with the managed quality gate and is gated by explicit authorization before the
next begins, matching this project's established slice convention — except a slice whose entire
diff is non-executable declarative metadata with no import-time or runtime effect (IR.1: a single
`pyproject.toml` `license` field), where confirming the file still parses is sufficient; see
`docs/project/README.md`'s Quality gates section for the exact boundary.

| Slice | Scope |
| :--- | :--- |
| IR.1 | License declaration fix (`pyproject.toml` → Apache-2.0, per the project owner's authorization above). `MOMENTUM.md`'s correction already landed ahead of this slice. |
| IR.2 | Unify the analyzer invocation envelope across all four analyzers (§2 item 3) and bring Momentum to full parity with the other three (§2 item 4). Large enough, and cutting across enough files, that it is itself split into five gated sub-slices by concern — never analyzer-by-analyzer — so that every sub-slice leaves all four analyzers mutually consistent and passes the full gate on its own. All five land on one branch, each as its own reviewed commit; nothing merges to `main` until the last one is accepted (§6.12). Full sub-slice list, scope, order, and dependencies: §6.12. Verified, not merely revisited, once Step 3.5's Piotroski analyzer is built against it (§5 item 7). |
| IR.3 | Momentum series API: pure vectorized series function beneath the existing snapshot API. Renumbered from IR.4 — the slice previously between it and IR.2 (Momentum quality-check/clock purity) is now part of IR.2 itself (§2 item 4), and IR.5 (JSON envelope models) moved to `SWC` (§2 item 6) — so this work package now has three slices, not five. |

## 4. Acceptance criteria

- No existing analysis's formulas or classifications change — verified by report, not by fixing:
  a calculation believed incorrect during IR.2 is reported to the project owner, not silently
  corrected here (that goes through the existing-strategy-correctness process). Exit codes and
  presentation *output* (what the CLI/orchestrator caller actually sees) do not change; the
  *internal* config/context shapes and persisted evidence/config schemas that produce that output
  may, per `AGENTS.md` §0 — version fields bump accordingly, with no migration or compatibility
  code for stored data during this consolidation period.
  **Accepted exception (IR.2.2, 2026-09-26):** `friendly_graham_failure`'s renaming to
  `friendly_valuation_failure` (§6.13.5 — the function generalizes as it moves to the neutral
  `evidence_presentation.py` module, ahead of NCAV/EPV/reverse-DCF strategies needing the same
  failure-prose helper) changed its wording from "the requested Graham inputs are invalid" to "the
  requested inputs are invalid." This is an investor-facing presentation-output wording change, not
  a formula, classification, or exit-code change — the failure is still reported under the exact
  same conditions, with the exact same status and exit code, just described without a now-inaccurate
  strategy name once the function is no longer Graham-specific. Recorded here rather than silently
  allowed, per this criterion's own "do not change" rule; every affected test assertion was updated
  to match, not left passing by coincidence.
- The complete managed gate (`scripts/run-quality-gates.ps1` / `.sh`), ≥85% coverage, after every
  slice that touches Python source, tests, or executable configuration. IR.1 is exempt per §3's
  sequencing note above.
- Each slice's own regression tests cover the specific defect it fixes; IR.2 additionally adds the
  conformance test described in §6.
- A final acceptance record analogous to this project's other work-package acceptance records,
  noting for IR.2 specifically: which persisted-shape version fields changed, and confirmation that
  no Alembic migration was required (§6).
- Before Step 3.5 implementation begins: the full ESC (Existing Strategy Correctness) audit matrix
  re-runs once IR as a whole is complete, to confirm no analysis result actually changed across the
  whole work package — not slice-by-slice, once at the end (per the project owner's direction).

## 5. Open questions for review

1. **Resolved (renamed from "IR.3" now that IR.3 the slice no longer exists):** Momentum's quality
   re-check becomes independent, trust-but-verify re-checking at both the resolution and calculation
   boundaries — landing inside IR.2 (§2 item 4) — not delegation to the resolver's earlier check.
2. **Moved to `SWC`, not resolved here.** This item scoped IR.5's schema-generation approach (real
   typed envelope models vs. hand-authored schemas, and whether it needs to split into two slices).
   IR.5 itself moved to `SWC` (§2 item 6); its scoping question travels with it and will be settled
   when `SWC`'s own contract is written, not in this document.
3. **Moved to `SWC`, not resolved here.** This item recorded IR.5's checked-in `schemas/` directory
   decision. Substance unchanged, but it now belongs to `SWC`'s eventual contract — see §2 item 6.
4. **Superseded by item 5.** This item originally proposed a suppression signal so `run_analysis`'s
   independent re-check wouldn't publish quality decisions the resolver already published, and left
   the exact signal as an open question for IR.3. Decided instead, per item 5.
5. **Resolved (2026-09-24), moved from IR.3 into IR.2:** the quality-check duplication is decided,
   not merely scoped: `run_analysis` re-checks independently using `context.effective_as_of` and
   does not publish; the
   resolver's own check (unchanged) remains the only publisher. No suppression signal is needed
   because there is no longer a second publish to suppress. `run_with_context` no longer exists as
   a separate method after IR.2 — its body *is* `run_analysis(ticker, config, context)`.
6. **Resolved:** the "public preloaded-frame API" this section previously worried about
   (`run_analysis`'s `df=` parameter, and whether an external caller might rely on it) was confirmed
   by inspection to have no production caller at all — only two test files
   (`tests/analysis/momentum/test_momentum_analyzer.py`,
   `tests/analysis/momentum/test_momentum_hardening.py`). IR.2 extracts that path into
   `compute_momentum_metrics`, a plain module-level function outside the `run_analysis`/`context`
   envelope entirely; both test files switch to calling it directly.
7. **Verification rule, not an open item (2026-09-24):** the `BaseAnalyzer[ConfigT, ResultT]`/
   `AnalysisContext` envelope is defined today only by retrofitting it onto four analyzers designed
   before it existed. Step 3.5's Piotroski F-Score analyzer — the first genuinely new analyzer built
   against it from scratch — is this envelope's verification, not an open question about it: if
   building Piotroski requires an envelope change, that change is made once and applies to all five
   analyzers (the four existing plus Piotroski) in the same piece of work, not accepted as a
   Piotroski-only special case or deferred as a known gap. See also §2 item 3.

## 6. IR.2 implementation inventory — approved 2026-09-24

This section is the call-site/field inventory required before IR.2 implementation began. Revised
twice on 2026-09-24 per `AGENTS.md` §0 (temporary consolidation-period authority): first for the
project owner's direction that every field in `AnalysisContext` have one meaning used identically by
all four analyzers, with no caller-dependent or "open" placement decisions left unsettled; then for
the conformance-check scope, the cache lazy-open design, the branching model, and the stale
references corrected in this second pass. Approved as the basis for implementation, which proceeds
slice by slice per §6.12, each stopped for review before the next begins. Line numbers are as of the
commit this inventory was written against; they will drift normally during implementation.

### 6.1 Problems verified against the code

1. **Confirmed.** `BaseAnalyzer.run_analysis(self, *args: Any, **kwargs: Any) -> ResultT` (the
   version briefly implemented and then discarded) constrains nothing; any override satisfies it.
2. **Confirmed.** `MomentumAnalyzer` declares `ResultT = MomentumMetrics` in the discarded version,
   but every production caller invokes `run_with_context`, which returns `MomentumRun`
   (`src/analysis/strategy/momentum/momentum_analyzer.py:144-172`).
   `src/workspace/execution.py:60` types the workspace's `NativeEvidence` union with `MomentumRun`,
   not `MomentumMetrics`.
3. **Confirmed.** `FCFEarningsGrowthAnalyzer.__init__` (`src/analysis/strategy/fcf_earnings_growth/analyzer.py:65-67`)
   never calls `super().__init__()` — moot once `BaseAnalyzer.__init__` is removed (§6.3).
4. **Confirmed.** `config_schema` is written (`graham_number/analyzer.py:16`,
   `graham_growth/analyzer.py:16`) but never read anywhere outside one test assertion
   (`tests/analysis/graham_value/test_method_analyzers.py:109`); `MomentumAnalyzer` never sets it at
   all despite the (non-abstract) base declaration requiring it structurally.
5. **Confirmed.** `src/orchestrator/analysis_tools.py:191-223` calls
   `run_graham_number_analysis`/`run_graham_growth_analysis` (the service-layer functions) directly,
   never constructing `GrahamNumberAnalyzer`/`GrahamGrowthAnalyzer`. The workspace path
   (`src/workspace/graham_number_execution.py:90`, `graham_growth_execution.py:105-107`) goes
   through the analyzer classes. Momentum and FCF do not have this split — both entry points already
   go through `MomentumAnalyzer`/`FCFEarningsGrowthAnalyzer`.
6. **Confirmed**, and more granular than stated: `as_of` lives on each strategy's persisted
   selection and analyzer config (Graham, FCF) or not at all (Momentum, which accepts none);
   `effective_as_of` is a real, consumed concept for FCF only (`analyzer.py:82-108`) and does not
   exist for Graham or Momentum; `use_cache` is a real per-call resolver parameter for Graham/FCF
   and does not exist for Momentum at all; `instrument_profile` is a construction-time,
   single-value-per-instance field for Graham, a per-call keyword for FCF, and for Momentum is
   either never attached to the returned `MomentumRun` (workspace path — profile travels
   separately) or attached after the fact via `dataclasses.replace()` (orchestrator path,
   `analysis_tools.py:184-185`). Full mapping in §6.4.
7. **Confirmed.** `analyzer.py:82`: `boundary = effective_as_of or as_of or datetime.now(UTC)`.
   Verified dead in every current production path — the orchestrator always computes and passes
   `effective_as_of` (`analysis_tools.py:234`), and the workspace adapter's `effective_as_of`
   parameter is required, not optional (`fcf_growth_execution.py:79`, no default). Only reachable
   today from a test that omits both `as_of` and `effective_as_of`.
8. **Confirmed**, with one correction: Graham's `_resolve_ticker` default-ticker fallback
   (`src/analysis/shared/graham_contracts.py:65-69`) is already unreachable in every production
   path — `src/cli.py`'s `graham-number`/`graham-growth`/`fcf-growth` commands resolve the ticker
   with `required=True` before calling the analyzer (`cli.py:364`, and the equivalent in
   `graham_growth`), and the orchestrator always requires a ticker via
   `_AnalysisToolArguments.ticker: str`. Momentum's TOML fallback **is** live in production: the
   `momentum` CLI command allows `ticker: str | None` with `required=False`
   (`cli.py:216-217,247`), and `run_momentum` constructs `MomentumAnalyzer(default_ticker=ticker, ...)`
   relying on its internal `self._fallback_ticker = default_ticker or default_section[ConfigKeys.TICKER]`
   (`momentum_analyzer.py:137`).
9. **Confirmed, and folded into IR.2 (decided 2026-09-24; clock value corrected 2026-09-26 —
   see §6.11).** `src/cli_composition.py:64-84`'s
   `build_graham_resolver` never passes `clock=` when constructing `GrahamNumberInputResolver`/
   `GrahamGrowthInputResolver`, so those resolvers fall back to their own un-injected default clock
   internally for quote-freshness evaluation (`QuoteFreshnessPolicy`). Per the project owner's
   direction — "the rule is one clock per run" — this is fixed, not escalated-and-left: every
   composition root that calls `build_graham_resolver` computes `executed_at` once, early
   (mirroring the pattern FCF's `cli.py:fcf_growth` command already uses for its own resolver
   clock), and passes it as the resolver's injected `clock=` — quote-freshness evaluation is a
   real-elapsed-time decision, so it reads `executed_at`, never `effective_as_of` (§6.11's corrected
   rule: `effective_as_of` is a cutoff passed as data, never wired through a `clock=` parameter).
   `effective_as_of` is supplied to `context` separately, unchanged. This closes the exception §6.3
   previously carved out for Graham: after this fix, all four analyzers' quote/freshness paths read
   `context.executed_at` (Graham and FCF via their resolvers' injected clock; Momentum directly),
   and every truncation/availability decision reads `context.effective_as_of` as data. Full plan:
   §6.12 (IR.2.3, clock unification, renumbered — §6.13 inserts Graham strategy separation as
   IR.2.2 ahead of it). Two
   more hardcoded `datetime.now(UTC)` calls surfaced while investigating this —
   `src/analysis/strategy/fcf_earnings_growth/input_resolver.py:234` and
   `src/data/financial/resolver.py:1236`, both inside shared quality-event-publishing helpers used
   by these same resolvers — fixed in the same slice by threading the same injected clock through
   (§6.12).
10. **New finding, revised 2026-09-24 — corrected after checking Step 3.3A's readiness-check
    interaction.** Graham and FCF today have *two* independent cache controls, not one:
    `cli_support.py:56-73`'s `_production_financial_cache(*, enabled: bool)` decides, at composition
    time, whether to build a durable `SQLiteResolvedInputCache` or a scratch
    `InMemoryResolvedInputCache()` that never persists across calls (and, when disabled, never opens
    or validates the SQLite database at all); separately, `src/data/financial/resolver.py`'s
    resolver methods take a per-call `use_cache: bool = True` that independently gates each
    read/write against whichever cache object was composed. **Regression check performed as
    directed:** removing the `enabled` switch naively (always eagerly calling
    `ensure_database_ready(database)` at composition time regardless of `use_cache`) would be a real
    regression — today, `--no-cache` works even when the database is missing or fails Step 3.3A's
    readiness checks, because it never opens the database at all; an eager "always wired" cache
    would make `--no-cache` newly *fail* on exactly that machine, where today it succeeds. **Revised
    design: the cache is always wired at composition, but opens storage lazily, on the first actual
    `.get()`/`.put()` call, not at composition time.** `_production_financial_cache()` (no
    `enabled` parameter) returns a cache object that defers `SQLiteDatabase(settings)`/
    `ensure_database_ready(database)` until its first real read or write; since the resolver's
    existing `if use_cache: ...`/`if use_cache and self._cache is not None: ...` gates already skip
    calling the cache at all when `use_cache=False` (unchanged by this work), a lazily-opening cache
    object means `use_cache=False` never touches storage, matching today's behavior exactly — the
    "always wired" part is the *object reference*, not an eager database connection.
    `CachedHistoricalDataClient`/Momentum's historical cache gets the identical treatment for
    symmetry, even though its current behavior (always wired, no `enabled` switch at all) doesn't
    have this specific regression risk today. Six `_production_financial_cache` call sites simplify
    to argument-less calls either way. Full plan: §6.12 (IR.2.5, cache unification, renumbered).
11. **Found and fixed during IR.2.1 implementation, not anticipated in this inventory.** Unifying
    the orchestrator's Graham Growth handler onto `GrahamGrowthAnalyzer` (removing its
    service-function bypass, §6.1 item 5) would have silently broken the Golden suite's SEC EDGAR
    FPI cases (`FPI-01`/`FPI-02`/`FPI-04`; tickers ASML/NTR/NVO), which request
    `eps_basis="fiscal_year"` — a real, documented capability
    (`docs/user/FINANCE_MATH.md` §"EPS basis": "Graham Growth using SEC EDGAR data uses
    three-year-average diluted EPS by default. The production tool boundary also supports an
    explicit single completed fiscal-year EPS basis for reviewed workflows.") that only ever
    worked because the orchestrator's bypass skipped `GrahamGrowthConfig`'s validation entirely —
    the CLI/workspace path (already Config-validated, unchanged by IR.2) has never exposed it.
    `_GrahamConfig`'s shared `eps_basis` validation was Graham-Number-shaped (SEC EDGAR:
    `three_year_average` only) and had no path for `fiscal_year` at all. **Decided (project owner,
    2026-09-25):** EPS-basis validation becomes genuinely method-specific — `_resolve_defaults`
    gains an `extra_allowed_sec_edgar_bases` parameter Graham Growth alone uses — rather than
    widening the shared rule for both methods (which would have wrongly let Graham Number accept
    `fiscal_year` too; `docs/user/GRAHAM.md`'s own EPS-basis convention documents
    three-year-average only for Number). `GrahamNumberEPSBasis`/`GrahamGrowthEPSBasis` type aliases
    in `graham_contracts.py` are now the single definition both the Config classes and the
    orchestrator's `GrahamNumberToolArguments`/`GrahamGrowthValueToolArguments` derive from — no
    more duplicated Literals that could drift apart. The identical duplicate business rule found in
    `src/workspace/requests.py`'s `_GrahamSelection._resolve_effective_configuration` got the same
    fix, so the CLI's `graham-growth --eps-basis fiscal_year` and `--save-run` now also work — a
    capability the CLI never exposed before, closing the entry-point gap rather than accepting it.
    Full Golden-suite and orchestrator-test re-run after the fix: all 3129 tests pass; only two
    test assertions needed updating, both for the (now more precise, multi-value) rejection message
    wording, not for any changed accept/reject outcome. No case's request was altered to force a
    pass. `docs/user/strategies/GRAHAM.md`'s EPS-basis section now states the per-method,
    per-provider table explicitly. This was validation matching already-documented, already-approved
    behavior, not a formula or classification change — in scope for IR.2.1 on that basis.
12. **Found and fixed during a subsequent IR.2.1 review pass: `AnalysisContext` collapsed two
    different concerns into one `effective_as_of` field.** Full description, rationale, and fix:
    §6 intro and §6.3/§6.4 above (revised 2026-09-25) — `AnalysisContext` now carries `executed_at`
    (the run's own single clock read) and derives `effective_as_of` (`as_of or executed_at`) as a
    read-only property, so freshness/TTL/timestamp consumers and data-truncation/availability
    consumers can no longer be silently fed the wrong one. IR.2.3's row (§6.12; clock unification,
    renumbered by §6.13's insertion of Graham strategy separation as IR.2.2) is updated to wire each
    consumer to the field matching its concern.
13. **Found and fixed during the same review pass: the EPS-basis accept/default rule was
    implemented twice, with `frozenset({"fiscal_year"})` repeated as a literal in both
    `GrahamGrowthConfig.validate_method` and `GrahamGrowthSelection._resolve_configuration`.**
    `_GrahamConfig._resolve_defaults` (analyzer-facing) and `_GrahamSelection._resolve_effective_configuration`
    (workspace-facing) each independently implemented the same accept/reject/default logic, with
    their own separately-worded error messages — exactly the kind of two-entry-point drift IR.2
    exists to close. **Fix:** both now delegate to one new function,
    `resolve_graham_eps_basis(eps_basis, security_provider_id, quote_provider_id, default_basis, *,
    extra_allowed_sec_edgar_bases)`, in `graham_contracts.py`; `GRAHAM_GROWTH_EXTRA_SEC_EDGAR_BASES`
    replaces the duplicated `frozenset({"fiscal_year"})` literal with one named constant both
    `GrahamGrowthConfig` and `GrahamGrowthSelection` import. `default_basis` stays an explicit
    parameter supplied by each call site, deliberately preserving each method's exact current
    default-resolution behavior (Graham Number's Config path always defaults `"three_year_average"`
    regardless of provider; Graham Growth's Config path and both Selection subclasses already used
    a provider-conditional default) — this fix does not change what any current call site accepts
    or defaults, only removes the duplicated mechanics and centralizes the error wording (the
    Selection-path messages now match the Config-path wording; `tests/workspace/test_requests.py`'s
    one message-substring assertion was updated to match — same finding-with-outcome-adjustment
    pattern as item 11, not a behavior change).
    **Separate, unresolved, out-of-scope finding surfaced while investigating this (report, not
    fix, per this file's "no formula/classification changes without explicit authorization"
    posture):** `GrahamNumberConfig`'s Config-path default (always `"three_year_average"`,
    unconditional on provider) and `GrahamNumberSelection`'s Selection-path default (provider-
    conditional, matching Graham Growth's pattern) already disagreed with each other before this
    session's changes — confirmed by direct reproduction:
    `GrahamNumberConfig(security_provider_id="massive", bvps_override=1.0)` raises
    (`"Massive requires eps_basis='ttm'"`) because the Config path always defaults to
    `"three_year_average"` first, while `GrahamNumberSelection(security_provider_id="massive",
    bvps_override=25.0)` succeeds and silently resolves `eps_basis="ttm"`
    (`tests/workspace/test_requests.py::test_graham_snapshot_is_independent_of_caller_inputs`
    already exercises and accepts this today). This predates IR.2.1 (confirmed via `git show`
    against the pre-IR.2 commit) and is a real behavioral divergence between the CLI direct-command
    path and the `--save-run`/workspace path for Graham Number with Massive and no explicit
    `--eps-basis` — not merely a duplicated-code smell. Resolving it either way is a business-rule
    decision (should the CLI direct path start auto-defaulting `ttm` for Massive like Growth
    already does, or should the Selection path start requiring it explicitly like Number's Config
    does), left to the project owner rather than decided unilaterally here.

### 6.2 Every production call site

Two production entry points exist per strategy: an **orchestrator handler**
(`src/orchestrator/analysis_tools.py`, also reused verbatim by the Golden evaluation suite via
`src/evaluation/composition.py`'s `compose_fixture_dependencies` → `register_analysis_tools`, which
is not a third entry point, just a second composition root for the same handlers), and a
**workspace execution adapter** (`src/workspace/*_execution.py`).

The workspace execution adapter itself has **two independent composition callers**, not one — this
was missing from the first version of this inventory. `src/cli.py`'s direct commands
(`graham-number`, `graham-growth`, `fcf-growth`, `momentum`) and `src/cli_workspace.py`'s
`_execute_graham_number`/`_execute_graham_growth`/`_execute_fcf_growth`/`_execute_momentum`
(dispatched by `_refresh_executor`, `cli_workspace.py:854-862`, for `ian refresh`) each
*independently* read `config.as_of`/`config.use_cache` (or `selection.as_of`/`selection.use_cache`)
to decide cache composition and presentation `as_of`, and each independently computes its own
`effective_as_of`-equivalent boundary. Full read-site list: §6.8.

| Strategy | Orchestrator handler | Workspace adapter | Composition callers |
| :--- | :--- | :--- | :--- |
| Momentum | `analyze_momentum` (`analysis_tools.py:171-185`) → `MomentumAnalyzer.run_with_context` | `run_momentum` (`momentum_execution.py:64-77`) → `MomentumAnalyzer.run_with_context` | `cli.py:286,303`; `cli_workspace.py:764-782` (`_execute_momentum`) |
| Graham Number | `analyze_graham_number` (`analysis_tools.py:187-203`) → `run_graham_number_analysis` (service function, bypasses `GrahamNumberAnalyzer`) | `execute_graham_number` (`graham_number_execution.py:60-92`) → `GrahamNumberAnalyzer.run_analysis` | `cli.py:862`; `cli_workspace.py:789-797` (`_execute_graham_number`) |
| Graham Growth | `analyze_graham_growth_value` (`analysis_tools.py:205-223`) → `run_graham_growth_analysis` (service function, bypasses `GrahamGrowthAnalyzer`) | `execute_graham_growth` (`graham_growth_execution.py:72-109`) → `GrahamGrowthAnalyzer.run_analysis` | `cli.py:937`; `cli_workspace.py:800-810` (`_execute_graham_growth`) |
| FCF/Earnings Growth | `analyze_fcf_earnings_growth` (`analysis_tools.py:225-245`) → `FCFEarningsGrowthAnalyzer.run_analysis` | `execute_fcf_growth` (`fcf_growth_execution.py:70-120`) → `FCFEarningsGrowthAnalyzer.run_analysis` | `cli.py:604`; `cli_workspace.py:815-834` (`_execute_fcf_growth`, which independently computes its own `boundary = selection.as_of or datetime.now(UTC)` — a *second*, separate now-dead-once-fixed fallback beyond the one in `analyzer.py:82`) |

### 6.3 Target types

```python
# src/analysis/base_analyzer.py


@dataclass(frozen=True)
class AnalysisContext:
    as_of: datetime | None
    executed_at: datetime
    use_cache: bool
    instrument_profile: InstrumentProfile | None = None

    @property
    def effective_as_of(self) -> datetime:
        return self.as_of or self.executed_at


class BaseAnalyzer[ConfigT, ResultT](ABC):
    """Abstract base class for all self-describing quantitative analysis strategies."""

    @abstractmethod
    def run_analysis(self, ticker: str, config: ConfigT, context: AnalysisContext) -> ResultT:
        """Execute the structural strategy with its own strategy-specific parameters."""
```

No `__init__`, no `default_ticker`, no `config_schema`. Each subclass defines its own constructor,
with every dependency (resolver, data client, calculation policy) injected and required — no
analyzer constructs a default client, reads `src.config.settings`, or calls `datetime.now`.

**Revised 2026-09-24: every field of `AnalysisContext` is read by all four analyzers, with no
exceptions.** Concretely: `executed_at` is the sole clock any analysis-layer code reads for
freshness/TTL/result-timestamp concerns — including, as of this round, Graham's resolver's
quote-freshness evaluation (§6.1 item 9, now folded into IR.2 rather than escalated); the derived
`effective_as_of` property is the sole point-in-time cutoff any analysis-layer code reads for data
truncation/availability concerns (§6.1 item 12); `use_cache` governs every cache read/write in all
four, including Momentum, which has none today (§6.9); `instrument_profile` is embedded in every
result, by every caller, uniformly (§6.4); `as_of`'s meaning is unchanged, and Momentum gains a
genuine `--as-of` CLI option to match the other three, not an inert placeholder field (§6.9). There
is no remaining exception — the earlier draft's Graham carve-out on the shared clock field is
closed.

### 6.4 Cross-cutting field placement: today → target (revised: one meaning, all four analyzers)

| Field | Momentum today | Graham (Number/Growth) today | FCF today | Target (all four) |
| :--- | :--- | :--- | :--- | :--- |
| `as_of` | `run_with_context(as_of=...)` param; no persisted field (`MomentumSelection` has none) | `_GrahamConfig.as_of` field on the persisted selection *and* the analyzer config (same field, same object today) | `run_analysis(as_of=...)` kwarg; `FCFGrowthSelection.as_of` persisted separately | `context.as_of`, unchanged meaning. Persisted selections keep their `as_of` field; `GrahamNumberSelection`/`GrahamGrowthSelection`/`FCFGrowthSelection` unchanged. `MomentumSelection` **gains** a persisted `as_of` field it did not have (see note below) so its selection shape matches the other three, consistent with "one meaning, used by all four" rather than "Momentum accepts none" remaining a caller-visible special case; `config_schema_version` bumps. The analyzer-facing `GrahamNumberConfig`/`GrahamGrowthConfig` **lose** the field (moves into context). |
| `executed_at` / `effective_as_of` | Does not exist | Does not exist; resolver's own clock (when injected at all — often not, §6.1 item 9) is separate from anything the analyzer sees | `run_analysis(effective_as_of=...)` kwarg, falls back internally to `as_of or datetime.now(UTC)` — the two concerns already collapsed into one value (§6.1 item 12) | `context.executed_at`, required, always caller-supplied — a single aware read of "now" taken once per run, the **sole clock** for freshness/TTL/result-timestamp concerns. `context.effective_as_of` (derived: `as_of or executed_at`) is the **sole point-in-time cutoff** every analyzer's resolution path reads for data truncation/availability. Momentum: quality re-check clock and result timestamp read `executed_at`; the resolver's `as_of`-bounded truncation reads `effective_as_of` as data, not a clock. FCF: its internal fallback is deleted outright; the resolver's injected clock is fed `executed_at` (its own event-timestamp use), and the truncation boundary it resolves against is `effective_as_of`, passed separately as data — the same cutoff embedded in the result, never wired through the clock. Graham: `build_graham_resolver` (and every composition root that calls it) now requires a `clock=` argument, computed once per call the same way FCF's `executed_at` already is, fed `executed_at` for the resolver's own clock and separately supplying `effective_as_of` as data wherever the resolver needs the truncation boundary — closing the exception the first pass of this inventory left open (§6.1 item 9). |
| `use_cache` | Does not exist anywhere (CLI, selection, resolver, or cache composition) | Two independent controls today, not one — see §6.1 item 10 | `run_analysis(use_cache=...)` kwarg | `context.use_cache`, the **single** control governing every cache read/write for the run, in all four analyzers. The durable cache is always wired at composition but opens storage lazily on first actual use (Graham/FCF's build-time `enabled` switch is removed — §6.1 item 10, revised to avoid a Step 3.3A readiness regression); the per-call flag alone decides read/write. Momentum gains this end-to-end, including a new `--no-cache` CLI flag and `MomentumSelection`/`MomentumToolArguments` fields — full plan in §6.9. |
| `instrument_profile` | Orchestrator: attached post-hoc via `dataclasses.replace(run, instrument_profile=profile)`. Workspace: never attached to `MomentumRun` — stays `None`; the resolved profile travels only via `MomentumCapture.profile`. | Construction-time, single value per analyzer instance | Per-call kwarg, embedded in the returned result | `context.instrument_profile`, embedded in every result by every caller — "the identity evidence for this run," regardless of whether the calculation consulted it. Momentum's `run_analysis` now sets `MomentumRun.instrument_profile = context.instrument_profile` unconditionally on every path; the orchestrator's `replace()` is deleted (no longer needed — the profile arrives already embedded); the workspace's `MomentumCapture`/`ExecutionCapture.profile` is read **from the result** (`run.instrument_profile`) rather than carried as a second, separately-composed value. This changes the persisted native-evidence shape for Momentum going forward — `MomentumRun`'s `result_schema_version` bumps (§6.10). |
| `security_provider_id` / `quote_provider_id` (Graham) | n/a | Orchestrator: fixed per deployment, no tool-argument field. Workspace: user-selected, persisted. | n/a | **Unchanged — stay on `GrahamNumberConfig`/`GrahamGrowthConfig`, per call**, per the project owner's direction (item 5). No tool-argument, CLI option, or persisted-selection schema change. |
| `provider_id` / `currency` (FCF) | n/a | n/a | Orchestrator: `provider_id` fixed; `currency` per-call. Workspace: both persisted on `FCFGrowthSelection`. | **New `FCFEarningsGrowthConfig` frozen dataclass** (`policy`, `currency`, `provider_id`) is FCF's `ConfigT`, per the project owner's direction (item 5) — kept, not folded into `FCFEarningsGrowthPolicy` (which `classify_fcf_earnings_growth` consumes directly). `FCFEarningsGrowthAnalyzer.__init__` stays `resolver`-only. |

Note on `MomentumSelection` gaining `as_of`: today Momentum's CLI command has no `--as-of` option at
all (only `graham-number`, `graham-growth`, and `fcf-growth` do). **Revised 2026-09-24, per the
project owner's explicit rejection of a placeholder field:** the capability already exists one layer
down — the orchestrator already passes `as_of` through to `MomentumAnalyzer.run_with_context`, and
`MomentumInputResolver.resolve` already truncates the fetched frame to it correctly (verified by
reading `momentum_analyzer.py:332-337`: `frame = frame.loc[timestamps <= pd.Timestamp(as_of)]`,
raising if nothing remains eligible) — only the CLI-level entry point was ever missing. `momentum`
gains a real `--as-of` option, in the same shape as the other three commands, and
`MomentumSelection.as_of` is wired to it, not left as an inert schema field. One caveat surfaced
while verifying this and recorded per the project owner's "report, don't fix" instruction for
anything calculation-adjacent: Momentum's historical prices come from a provider that revises
adjusted closes retroactively (splits/dividends restate history), so a `momentum --as-of <date>`
result reflects *today's* adjusted view of prices at that date, not the exact values that were
knowable on that date — an `as_of` result is filtered to a point in time, not a strict point-in-time
snapshot of what the market showed then. This is a data-provider property, not a bug in the
resolver's truncation logic, which does exactly what it claims. `MOMENTUM.md` gains a note recording
this distinction (§6.9).

### 6.5 Design decisions confirmed or revised in this pass

- **Confirmed as designed:** `FCFEarningsGrowthConfig` is a new wrapper type, not an extension of
  `FCFEarningsGrowthPolicy` (§6.4 FCF row), and Graham's/FCF's provider identifiers stay in
  `ConfigT`, not construction — both explicitly kept per the project owner's direction (item 5).
- **`AnalysisContext` lives in `src/analysis/base_analyzer.py`**, unchanged from the first pass.
- **Revised: Momentum's `instrument_profile` is no longer preserved asymmetrically.** The first
  version of this inventory kept the workspace path's `MomentumRun.instrument_profile` at `None` to
  avoid changing the persisted evidence shape. Per the project owner's explicit instruction, that
  asymmetry is now unified instead: every analyzer's result carries the profile, meaning "the
  identity evidence for this run" regardless of whether the calculation consulted it. This is a
  deliberate persisted-shape change, authorized under `AGENTS.md` §0 — `MomentumRun`'s
  `result_schema_version` bumps (§6.10) rather than being protected from change.
- **Momentum's `run_analysis` absorbs `run_with_context`'s body**, but no longer "exactly" — the
  quality-check/clock/telemetry logic is restructured per §2 item 4 (resolver checks-and-publishes
  once; `run_analysis` re-checks `as_of`-aware via `context.effective_as_of` without publishing) as
  part of this same slice, not deferred to IR.3. The frame-based calculation becomes
  `compute_momentum_metrics(df, config, ticker, timestamp) -> MomentumMetrics` — genuinely pure: no
  quality check, no telemetry, no clock read, no logger; `timestamp` is a plain parameter sourced
  from `context.effective_as_of` by the caller. The two tests that call the old
  `run_analysis(..., df=...)` directly switch to calling `compute_momentum_metrics`.
- **Ticker-default relocation only has real work to do for Momentum**; Graham's `_resolve_ticker`
  fallback is deleted outright (not just left unreachable — per the project owner's direction, item
  3) since it was already dead in every production path (§6.1 item 8). Momentum's CLI command gains
  its own resolution of the same TOML default, currently read inside `MomentumAnalyzer.__init__`;
  `run_momentum`/`capture_momentum`'s existing `ticker: str | None` parameter and "configured
  default ticker" display label are unaffected.
- **New: dependencies become injected and required (item 3).** `MomentumAnalyzer.__init__` loses
  its `client = data_client or YFinanceClient()` default and its two `settings.get_analysis_settings()`
  reads (`_start_date`, the TOML ticker default). Every composition root — `cli.py`, `cli_workspace.py`,
  `src/orchestrator/analysis_tools.py`'s dependency composition, `src/evaluation/composition.py` —
  now supplies `data_client`/`market_data_provider` and `start_date` explicitly. None of these roots
  need a new value they don't already have: `cli.py`/`cli_workspace.py` already construct
  `YFinanceClient()` and read `settings` themselves nearby; the orchestrator's and evaluation's
  compositions already inject `MomentumAnalyzer` once at startup and can read `start_date` from
  settings there instead. This is a pure relocation of an existing read, not a new capability.
- **New: `_execute_fcf_growth`'s duplicate `datetime.now(UTC)` fallback in `cli_workspace.py`
  (§6.2) is also deleted**, not just the one inside `analyzer.py` — both compute the same kind of
  value (`boundary`/`effective_as_of`) and both become `context.effective_as_of`, derived once by
  whichever composition root is running, per §6.8's mapping.

### 6.6 Conformance test plan

A new parametrized test module (proposed: `tests/analysis/test_base_analyzer_conformance.py`)
covering, for each of the four analyzers:
1. `issubclass(AnalyzerClass, BaseAnalyzer)`.
2. `run_analysis`'s signature (via `inspect.signature`) matches `(self, ticker: str, config: ConfigT, context: AnalysisContext) -> ResultT` exactly — parameter names, kinds, and annotations.
3. Calling `run_analysis` with fakes (no network; reusing each strategy's existing fixture-backed test doubles) returns an instance of the analyzer's declared `ResultT` (read from `__orig_bases__`/`get_args`, not asserted by hand per analyzer).
4. **Revised to a general rule, not a name list, per the project owner's direction (item 6):** a
   structural scan (AST-based, over every `.py` file under `src/` excluding `src/analysis/strategy/**`
   itself) asserting that no `from src.analysis.strategy...` import anywhere outside that package
   binds a plain function — only classes (including dataclasses, enums, and Pydantic models) may be
   imported across that boundary. This is strictly more general than the specific-name list it
   replaces, so it also catches any future strategy-internal function a later change might otherwise
   leak across the boundary by accident.
   **Exceptions surveyed and found: zero, once IR.2's own fix lands.** Every current
   `from src.analysis.strategy...` import outside `src/analysis/strategy/` was enumerated by
   grepping the whole `src/` tree; the only plain-function imports found anywhere are
   `run_graham_number_analysis`/`run_graham_growth_analysis` in
   `src/orchestrator/analysis_tools.py:22,24` — exactly the two imports IR.2 itself removes (§6.1
   item 5). Every other cross-boundary import in the codebase today (`GrahamNumberAnalysis`,
   `GrahamGrowthAnalysis`, `MomentumRun`, `MomentumMetrics`, `MomentumConfig`, `GrahamNumberConfig`,
   `GrahamGrowthConfig`, `FCFEarningsGrowthResult`, `FCFEarningsGrowthPolicy`,
   `GrahamNumberInputResolver`, `GrahamGrowthInputResolver`, `GrahamGrowthCalculationPolicy`,
   `ProductionAnnualGrowthSeriesResolver`, the four analyzer classes, `GrahamNumberInputAssembly`,
   `GrowthValueInputAssembly`, `GrahamNumberResult`, `GrahamGrowthValueResult`, `HistoricalHorizon`,
   and others) is a class, dataclass, enum, or model — never a function. No exceptions to bring to
   the project owner for approval; the rule can be adopted with none.
   Scoped to `src/` only — tests may still exercise calculation functions directly (e.g. existing
   `tests/analysis/*/test_calculation*.py`), which is normal unit testing, not the production-bypass
   problem being guarded against.
5. **New, per the project owner's direction (item 3): no bare clock calls outside the composition
   roots.** A structural scan asserting no `datetime.now`, `datetime.utcnow`, or `time.time()` call
   exists anywhere under `src/`, except in an explicitly allowed set of modules. Full inventory of
   every current call site, the reasoning behind which modules are allowed, and the exact allow-list:
   §6.11.

### 6.7 Known affected test files (non-exhaustive; finalized during implementation)

`tests/analysis/graham_value/test_method_analyzers.py` (rewrites the service-equivalence assertion
that reads `config.model_dump()` including `as_of`/`use_cache`, and the `config_schema` assertion),
`tests/analysis/momentum/test_momentum_analyzer.py`, `tests/analysis/momentum/test_momentum_hardening.py`
(switch to `compute_momentum_metrics`), `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_analyzer.py`,
`tests/orchestrator/test_analysis_tools.py`, `tests/evaluation/cases/test_graham_g3.py`,
`tests/analysis/test_instrument_applicability.py`, `tests/test_cli_historical_cache.py`,
`tests/test_existing_strategy_output_contracts.py`, `tests/reporting/test_security_identity_presenters.py`,
`tests/analysis/fcf_earnings_growth/test_sec_edgar_analysis_snapshot.py`,
`tests/workspace/test_momentum_codec.py` (new `instrument_profile`/`result_schema_version` shape),
`tests/workspace/test_execution.py`, `tests/workspace/test_requests.py` (`MomentumSelection` gains
`as_of`/`use_cache` fields), `tests/analysis/momentum/test_momentum_hardening.py` (also switches its
`MomentumPolicy` construction to `MomentumConfig`), `tests/test_cli_historical_cache.py` and any
Graham/FCF cache-composition test asserting `_production_financial_cache`'s `enabled=` keyword
(signature loses it entirely), any test asserting `build_graham_resolver`'s current no-clock
construction (gains a required `clock=` argument). New coverage: the `momentum` command's new
`--as-of`/`--no-cache` options (extending existing momentum CLI test files rather than a new one),
and the datetime-now/import-boundary conformance tests themselves (§6.6 items 4–5). The full list
(with a one-line reason per file) will be reported after implementation, per the project owner's
request.

### 6.8 CLI/`cli_workspace` reads of `config.as_of`/`config.use_cache`, and the consolidated selection mapping (item 4; confirmed, item 2)

Every one of these reads a field IR.2 removes from the analyzer-facing `Config` types (`as_of`,
`use_cache` move to context) and must be repointed at a local variable or `context` field instead.
None of these are new call sites — they were always part of §6.2's composition callers, just not
individually enumerated in the first pass.

| Site | Today | Fix |
| :--- | :--- | :--- |
| `cli.py:391` (`graham-number`) | `_production_financial_cache(enabled=config.use_cache)` | `_production_financial_cache()` — the `enabled` parameter is removed entirely (§6.1 item 10); the cache is always wired, so there is nothing left to read `config.use_cache` for at this call site. |
| `cli.py:499` (`graham-growth`) | Same pattern, same fix. | Same fix. |
| `cli.py:858-869` (`_run_graham_number`, reading `as_of = config.as_of` for `GrahamNumberPresentation`) | Reads `config.as_of` for presentation. | `as_of = boundary` (or `selection.as_of`, once the consolidated mapping below lands) — one value, one source, not re-derived from a `config` field that no longer carries it. |
| `cli.py:933-944` (`_run_graham_growth`, same pattern) | Same. | Same fix. |
| `cli_workspace.py:794` (`_execute_graham_number`) | `_production_financial_cache(enabled=config.use_cache)` | `_production_financial_cache()`, same fix as above. |
| `cli_workspace.py:807` (`_execute_graham_growth`) | Same pattern. | Same fix. |

`cli_workspace.py:815-834`'s `_execute_fcf_growth`'s `_production_financial_cache(enabled=selection.use_cache)`
gets the identical fix; its separate duplicate `datetime.now(UTC)` fallback is fixed per §6.1 item 9.

**Confirmed: one explicit mapping per strategy, used by both CLI composition roots (item 2).**
`cli.py`'s direct-command path currently re-derives `config` from raw CLI arguments
(`GrahamNumberConfig.model_validate({...})`) *and* separately builds `selection` from the same raw
arguments (`GrahamNumberSelection(...)`, for the `request_factory` used only when saving) —
duplicated construction of the same values. Per the project owner's confirmation, IR.2 removes this
duplication: `cli.py`'s direct path builds `selection` first (as it already does), then derives
`config`/`context` from `selection` via one method each per strategy
(`to_graham_number_config()`/`to_graham_growth_config()`/`to_momentum_config()`/a new FCF
equivalent building `FCFEarningsGrowthConfig`, unchanged in spirit, plus a new
`to_analysis_context(executed_at, instrument_profile=None)` on every `*Selection` class), and
`cli_workspace.py`'s refresh path calls the exact same methods. Both composition roots use one
shared mapping per strategy, not independently-maintained parallel construction.

### 6.9 Momentum's historical cache control (inventoried per the project owner's direction, item 1)

**Today: Momentum's historical data is unconditionally cached, with no control anywhere.** Unlike
Graham/FCF (`_production_financial_cache(*, enabled: bool)`, driven by `config.use_cache`/`--no-cache`),
Momentum's composition (`cli_support.py:35-53`, `_production_historical_client`) always wraps the
provider in `CachedHistoricalDataClient` with no `enabled`/bypass parameter, and the `momentum` CLI
command has no `--no-cache` option, no `use_cache` field on `MomentumSelection`, and no `use_cache`
field on `MomentumToolArguments`. Caching is a structural (composition-time) property of which
client object gets built, not a runtime toggle.

**Why a composition-time toggle (mirroring Graham/FCF's `_production_financial_cache(enabled=...)`
pattern exactly) is not sufficient here:** Graham/FCF resolvers are also constructed fresh per call
in every entry point, so composition-time toggling works for them everywhere. Momentum's
orchestrator entry point is different — `AnalysisToolDependencies.momentum_analyzer` is one
long-lived `MomentumAnalyzer` instance, constructed once with one injected `market_data_provider`,
reused for every tool call. A composition-time-only toggle cannot vary per call for that instance.
Since the project owner's instruction is that `use_cache` "governs every cache read and write for
the run" (per-run, not per-analyzer-lifetime), the control needs to be a genuine per-call parameter
threaded through to `CachedHistoricalDataClient`, not just a choice of which object to inject once.

**Proposed plan:**
1. `BaseDataClient`/`MarketDataProvider` (`src/data/base_client.py:34,50,70`, `src/data/market_data.py:44`)
   gain a `use_cache: bool = True` parameter on `fetch_data`/`fetch_data_with_context`/`fetch_historical_data`.
2. `CachedHistoricalDataClient.fetch_data_with_context` (`src/data/cached_client.py:100`) reads it:
   `use_cache=False` skips the repository `GET` (always fetches live) and skips the repository `PUT`
   (never writes), mirroring `src/data/financial/resolver.py`'s existing `if not use_cache` /
   `if use_cache and self._cache is not None` pattern for Graham/FCF exactly.
3. `YFinanceClient` and the evaluation fixtures (`FixtureDataClient`, `FixtureMarketDataProvider`)
   accept and ignore the parameter (they have no cache of their own — same shape as Graham's
   resolver methods accepting `use_cache` even on paths where it has nothing to skip).
4. `_ClientProviderAdapter` (`momentum_analyzer.py:401-415`) and `MomentumInputResolver.resolve`
   (`momentum_analyzer.py:308+`) thread it through from `context.use_cache`.
5. New surface, matching Graham/FCF's existing shape exactly: a `--no-cache` option on the
   `momentum` CLI command; a `use_cache: bool = True` field on `MomentumSelection` (persisted,
   `config_schema_version` bumps — no Alembic migration, §6.10) and on `MomentumToolArguments`.
6. `MomentumAnalyzer`'s data-fetch call inside the (now-unified) `run_analysis` passes
   `context.use_cache` through to the resolver/provider call.

**Confirmed: full thread-through, no fallback (item 1).** A known gap is not acceptable under
`AGENTS.md` §0's consolidation-period rule; the composition-time-only alternative previously offered
is withdrawn. This is the single largest piece of scope growth in this work package — it touches the
data-client protocol layer, not just the analyzer envelope — which is exactly why it is its own
gated sub-slice (IR.2.5, cache unification, renumbered — §6.12) rather than folded silently into the
envelope slice.

**Momentum's `--as-of` CLI option (item 4) lands alongside this work**, since both are the same kind
of gap: a capability the analyzer/resolver already supports correctly but the CLI never exposed
(the orchestrator path already wires `as_of` today — §2 item 4's real-`as_of` bullet). `MomentumSelection`
gains real `as_of: AwareDatetime | None = None` and `use_cache: bool = True` fields together
(§6.10's version bump covers both in one `config_schema_version` step, not two);
`MomentumToolArguments` gains only `use_cache`. `docs/user/strategies/` gets a note (in `MOMENTUM.md`
or the nearest equivalent — final location confirmed during implementation) recording that
provider-adjusted
historical prices are revised retroactively, so a `momentum --as-of <date>` result reflects today's
adjusted view of prices at that date, not a strict point-in-time snapshot of what was knowable then
(§6.4's `as_of` row).

### 6.10 Persisted-shape version bumps and Alembic (per the project owner's direction, item 7)

**No Alembic migration is needed for any change in this revised inventory.** Confirmed by reading
`src/data/repositories/schema.py`: `AnalysisRun`'s native evidence, requested/effective config, and
instrument-profile snapshot are all serialized into one `envelope_json TEXT` column
(`schema.py:426`); watchlist selections are similarly stored as one `selection_json TEXT` column
per entry (`schema.py:389,478`). Every version field this inventory bumps
(`MomentumSelection.config_schema_version`, `MomentumRun`'s `result_schema_version` via
`execution.py`'s `_METHOD_VERSIONS[("momentum", "sma_crossover")]`) is an existing, already-versioned
integer column — changing what integer gets written and what shape the JSON blob it accompanies
takes is a data change, not a schema change. No new table, no new column, no `alembic revision`.

**Version fields that change:**
- `MomentumSelection.config_schema_version`: `1` → `2` (persisted selection gains `as_of`,
  `use_cache` fields).
- `execution.py`'s `_METHOD_VERSIONS[("momentum", "sma_crossover")]`: `(1, 1)` → `(1, 2)`
  (`result_schema_version` bumps because `MomentumRun.instrument_profile` is now always populated
  from `context.instrument_profile` rather than sometimes staying `None`; `method_version` is
  unchanged since the calculation itself is unchanged).
- `codecs.py`'s `decode_evidence` version-check logic currently expects `result_schema_version == 1`
  for every non-FCF method via one shared literal (`3 if fcf_pair else 1`). This needs restructuring
  to give Momentum its own branch (`2`) distinct from Graham's (still `1`) — noted here so the
  implementer doesn't just flip the shared literal and silently break Graham's version check.

No other strategy's persisted version fields change: Graham Number/Growth's `GrahamNumberConfig`/
`GrahamGrowthConfig` lose fields, but `GrahamNumberSelection`/`GrahamGrowthSelection` (the persisted
type) do not change shape, so their `config_schema_version` stays `1`; their `result_schema_version`
is unaffected since `GrahamNumberAnalysis`/`GrahamGrowthAnalysis` gain no new populated field. FCF's
`FCFGrowthSelection` is unaffected (unchanged persisted shape); `FCFEarningsGrowthResult` is
unaffected (its `instrument_profile` was already always populated).

### 6.11 `datetime.now`/`datetime.utcnow`/`time.time` audit, classified by purpose, and the shared-clock helper (item 3, revised 2026-09-24; clock rule corrected 2026-09-26)

**Revised per the project owner's explicit rejection of the narrowed-scope recommendation.** The
Category-C "already injectable, defaults to the wall clock" pattern is not a safe exception — it is
exactly how the Graham resolver bug (§6.1 item 9) happened: an injectable clock that no production
composition root ever actually injected, silently falling back to `datetime.now`. The distinction
that matters is not "injectable vs. hardcoded," it is **what the clock value is used for**:

**Corrected 2026-09-26 — every injected clock receives `context.executed_at`; `effective_as_of` is
never a clock.** An earlier pass of this section fed every "decision clock" from
`context.effective_as_of`, including cache/TTL freshness checks. That is wrong: TTL freshness answers
"how much real time has elapsed since this was cached," which must be judged against the run's actual
execution clock, not the requested historical boundary — feeding a historical `effective_as_of` into
a TTL comparison would make a cache entry's judged age track the requested `--as-of` date instead of
how long ago it was actually written, unrelated to whether the historical fact it holds is itself
still eligible. `effective_as_of` is the point-in-time **cutoff** for data-truncation/availability
decisions (was this fact knowable by the requested boundary); it is passed as an ordinary data
argument wherever that specific decision is made, and never wired through a `clock: Callable[[],
datetime]` constructor parameter.

- **Decision clocks** — cache/TTL freshness evaluation, quality checks — become **required** injected
  parameters, no default, fed from `context.executed_at` by whichever composition root is running
  (the same "one value, two injection points" pattern already established for Graham's resolver,
  §6.1 item 9, corrected here to the right value). Where the same class also needs the requested
  point-in-time cutoff for an `as_of`-based availability/eligibility decision (SEC EDGAR's filing
  eligibility, below), that cutoff is a separate, ordinary method/call argument fed
  `context.effective_as_of` as data — never the injected clock.
- **Event timestamps** — recording when something actually happened (a row was written, a provider
  response was received, a telemetry span was recorded, a log line was rotated) — may still use the
  real wall clock, but **only** through one shared helper, `src/core/clock.py`'s `utc_now() -> datetime`
  (new module), never an inline `datetime.now(UTC)`/`datetime.utcnow()`/`time.time()` call. `utc_now()`
  and `context.executed_at` read the same underlying clock; `utc_now()` is for call sites that read it
  directly rather than through an injected `AnalysisContext`.

Every call site under `src/` (excluding tests), reclassified on that basis. Files whose clock
**feeds even one decision use** become required-no-default overall, even where the same clock also
happens to stamp an event timestamp — a constructor parameter cannot be "sometimes required."

**Decision clocks → required, no default, fed from `context.executed_at`:**

| File / class | What it decides |
| :--- | :--- |
| `src/data/cached_client.py` (`CachedHistoricalDataClient`) | Historical-cache freshness/TTL and quality evaluation (`_quality_error`), judged against real elapsed time. |
| `src/data/financial/cache.py` | Resolved-input cache freshness/TTL evaluation (line 465's conditional `datetime.now(UTC)` fallback is removed along with the default — the clock is always available once required), judged against real elapsed time. |
| `src/data/financial/resolver.py` | Financial-fact quality/freshness checks (`financial_quality_error`, `evaluate_quote_freshness`, `stored.available_at > self._clock()`) judged against real elapsed time; its class-level `_DEFAULT_CLOCK` is removed. The Category-B `_event` helper (§6.1 item 9's note, line 1236) is the same file, same fix. |
| `src/data/instrument_profile_cache.py` (`CachedInstrumentProfileResolver`) | Instrument-profile cache freshness/TTL evaluation (`_is_fresh`), judged against real elapsed time. |
| `src/data/repositories/resolved_input_cache.py` (`SQLiteResolvedInputCache`) | Same TTL freshness decision as `financial/cache.py`, at the repository layer (line 284's conditional fallback removed the same way), judged against real elapsed time. |
| `src/data/sec_edgar/financial_facts.py` | This file's `self._clock()` calls (lines 235, 343, 532) are pure event uses, now fed `executed_at`. `provider_now` (line 429) currently reuses the same injected clock to feed `_eligible_annual_candidates(..., now=...)` — a point-in-time *eligibility* decision (was this filing available by the requested boundary), which is an `effective_as_of` concern, not a clock. That call site changes to take the boundary as an explicit argument fed `context.effective_as_of`, separate from the class's own `executed_at`-fed clock; the constructor's clock parameter stays required (for the three event uses), but stops doubling as the eligibility boundary. |

**Event timestamps → keep a default, routed through `utc_now()`:**

| File / class | What it stamps |
| :--- | :--- |
| `src/data/yfinance/client.py` | `resolved_at`/metadata-snapshot timestamp (line 223) and the hardcoded `retrieved = datetime.now(UTC)` (line 116) — both become `utc_now()`. |
| `src/data/massive/financial_facts.py` | `retrieved_at` only, no decision use found. |
| `src/data/yfinance/financial_facts.py` | `retrieved_at` only, no decision use found. |
| `src/data/repositories/instrument_profiles.py` | Row timestamp only — freshness/TTL policy is explicitly documented as the caller's concern (`instrument_profiles.py:9`, owned by `instrument_profile_cache.py` above), not this repository's. |
| `src/data/repositories/market_data.py` | `cached_at` row timestamp only. |
| `src/data/repositories/watchlists.py` | `created_at`/`updated_at` row timestamps only. |
| `src/workspace/execution.py` | `AnalysisRun.started_at`/`completed_at`. |
| `src/workspace/refresh.py` | Refresh-batch timing, same shape. |
| `src/core/telemetry/recorder.py` | Telemetry span timestamp — trajectory logging is a separate concern from deterministic analysis (`MASTER_PLAN.md` §11.5), but "telemetry" is explicitly named as an event-timestamp category, so this routes through `utc_now()` too rather than being exempted. |

**`src/utils/logger_util.py`'s three `time.time()` calls (log-rotation scheduling) — flagged, not
silently included.** These are float epoch comparisons for rollover timing, not `datetime` values,
and operational logging is explicitly a different concern from analysis telemetry per `AGENTS.md`
§6 ("do not perform an unrelated logging migration unless the active task owns it"). `utc_now().timestamp()`
would be behavior-equivalent to today's `time.time()`, so routing through the shared helper is
mechanically possible without changing rotation behavior — but this is operational logging, not an
analysis or telemetry clock, and folding it into a "one clock per run" effort reads as exactly the
unrelated-logging-migration `AGENTS.md` §6 warns against. **Recommendation: exempt this one file by
name in the conformance check** (not by category — every other event-timestamp site above is in
scope), and record the exemption explicitly rather than silently widening `src/core/clock.py`'s
purpose to cover log rotation. Say if this should be included instead.

**Conformance-check shape (revised): scan all of `src/`** for `datetime.now`, `datetime.utcnow`,
`time.time()`, failing on any match — **`src/core/clock.py` itself is the only exception** (where
`utc_now()` is defined and necessarily calls the real clock once), plus the named
`src/utils/logger_util.py` exemption above pending confirmation. Every decision-clock class's
newly-required `clock` parameter is satisfied by every composition root
(`cli.py`, `cli_workspace.py`, `cli_composition.py`, `src/evaluation/composition.py`) passing
`lambda: executed_at` (or the resolved value directly, matching whatever shape each constructor
already expects) — the same single clock read the composition root takes once per run and that
becomes `context.executed_at` for the analyzer call in the same invocation. Where a class also needs
the truncation/eligibility boundary (SEC EDGAR's `_eligible_annual_candidates`, above), that boundary
is passed as a separate, ordinary argument fed `context.effective_as_of` — not through this clock.

**Slice placement (revised — see §6.12): this is materially larger than clock unification's
original Graham-resolver-clock scope** — six classes made non-optional, nine files migrated to a new
shared helper, one new module, and every composition root touched to supply the now-mandatory
decision clocks. Given the choice offered, this lands as its **own slice, immediately after clock
unification** (originally numbered IR.2.2/IR.2.3; both renumbered to IR.2.3/IR.2.4 once §6.13
inserted Graham strategy separation as IR.2.2, cache unification and Momentum parity shifting to
IR.2.5/IR.2.6 in turn) — it depends on clock unification having already established the "compute
`executed_at` once per run, derive `effective_as_of` from it, thread each to the consumer that needs
it" composition-root pattern for Graham, but touches enough
additional files (`src/data/**` broadly) that folding it into
clock unification itself would make that slice unreviewable in one pass.

### 6.12 IR.2 slice list (item 8) — approved, revised 2026-09-25 (Graham separation inserted)

Split by concern across all four analyzers, never analyzer-by-analyzer, per the project owner's
explicit instruction; revised 2026-09-25 to six slices — **IR.2.2, Graham strategy separation
(full plan: §6.13), is a new sub-slice inserted before clock unification**, per the project owner's
explicit direction: Graham Number and Graham Growth Value answer different questions with different
formulas (`MASTER_PLAN.md` principle 9 already treats them as separate methods), the shared
`_GrahamConfig`/`_GrahamSelection`/`graham_contracts.py` base has caused repeated partial fixes
(§6.1 items 11 and 13), and doing the split before clock unification means IR.2.3 (old IR.2.2)
wires Graham's resolver clock into two clean, independent strategy packages rather than into a
shared base mid-transition. Every slice below still leaves all four analyzers mutually consistent
with each other and passes the full managed gate before the next begins — the project's standard
gated-slice convention (§3), applied one level deeper than usual because IR.2 itself is large
enough to need it.

**Branching (item 3):** all six sub-slices land on one branch, each as its own reviewed commit with
its own gate run. Nothing merges to `main` until IR.2.6 is done — the intermediate states between
sub-slices have `AnalysisContext` fields some analyzers don't yet honor (e.g. after IR.2.1 but
before IR.2.3, Graham's resolver still reads no clock), which is an acceptable mid-branch state but
not one to expose on `main`.

| Slice | Scope | Depends on | Leaves all four analyzers... |
| :--- | :--- | :--- | :--- |
| **IR.2.1 — Envelope and single entry point** | `AnalysisContext`/`BaseAnalyzer[ConfigT, ResultT]` (§6.3); every analyzer's `run_analysis(ticker, config, context)` signature; `FCFEarningsGrowthAnalyzer` brought under `BaseAnalyzer` with the new `FCFEarningsGrowthConfig`; the orchestrator's Graham handlers unified onto the analyzer classes (removing the service-function bypass, §6.1 item 5); ticker required everywhere, Graham's `_resolve_ticker` fallback deleted (§6.1 item 8); the consolidated selection→`(config, context)` mapping used by both `cli.py` and `cli_workspace.py` (§6.8). Structural conformance tests land here (§6.6 items 1–4). At this slice's boundary, `context.effective_as_of`/`context.use_cache` exist and are threaded to wherever each analyzer already had an equivalent parameter, but Graham's resolver clock, the Graham strategy split, the broader data-layer clock consolidation, and Momentum's cache/quality-check/profile/dependency work are *not* yet done — those are 2.2–2.6. | — (foundational) | ...on one invocation shape, with `context` fully defined and consumed wherever an equivalent concept already existed. |
| **IR.2.2 — Graham strategy separation** | Full plan: §6.13. `graham_contracts.py`, `_GrahamConfig`, `_GrahamSelection`, and its `GrahamMethod` tag are removed entirely; Graham Number and Graham Growth Value each own their complete config, selection, EPS-basis acceptance rule and defaults, result, and presentation, with zero shared Graham-specific code. Genuinely general behavior moves to neutral homes: provider EPS-basis capability to a new `src/data/financial/eps_basis.py` (also fixing §6.1 item 13 — one provider-driven default rule, `three_year_average` for SEC EDGAR, `ttm` for everything else including Massive, applied identically by both methods at every entry point); quote resolution and the price-relationship comparison stay in the already-neutral `financial_resolution.py`; a new `src/reporting/valuation_presentation.py` absorbs the reporting helpers shared today, ahead of NCAV/EPV/reverse-DCF needing the same presentation primitives; `reporting/graham.py` splits into `reporting/graham_number.py`/`reporting/graham_growth.py`. Each method gets its own `analysis_id` (`graham_number`, `graham_growth_value`, matching its existing `method_id`) with version-field bumps (§6.10 pattern); the Golden suite's separate `graham_method_selection` evaluation category folds into ordinary strategy-selection (§6.13.7). `GRAHAM.md` splits into `GRAHAM_NUMBER.md`/`GRAHAM_GROWTH.md` plus a short linking overview; the milestone exit criteria's "Graham method-selection" metric becomes ordinary tool selection. No formula, classification, or result changes — the Golden suite passes unchanged apart from identifiers. | IR.2.1 | ...with each Graham method a complete, independent, equally-good example of implementing a strategy — no shared Graham-specific base for anything downstream to build on by habit. |
| **IR.2.3 — Clock unification (analyzer/resolver layer)** | Every consumer in `src/analysis/**` is wired to the field matching its own concern, per §6.1 item 12: freshness/TTL/result-timestamp reads use `context.executed_at`; data-truncation/availability reads use `context.effective_as_of` (the derived cutoff). Graham Number's and Graham Growth's now-independent resolvers each gain an injected clock from their own composition-root construction, fed `executed_at` (never `effective_as_of` — that stays a separate data argument wherever the resolver needs the truncation boundary, §6.1 item 9); FCF's internal fallback and `cli_workspace.py`'s duplicate are deleted, both replaced by the composition root's single `executed_at` read plus the derived `effective_as_of` passed as data; the two Category B hardcoded quality-event calls (§6.11) are fixed to read `executed_at`; Momentum's quality-check/clock restructuring lands (resolver checks-and-publishes once using `effective_as_of` as data for its `as_of`-aware truncation, `run_analysis` re-checks independently without publishing, `compute_momentum_metrics` extracted as a genuinely pure function, §2 item 4). Establishes the "compute `executed_at` once per run, derive `effective_as_of` from it, thread each to the consumer that needs it" composition-root pattern that IR.2.4 extends more broadly. | IR.2.1, IR.2.2 (touches two clean, independent Graham packages, not a shared base mid-transition) | ...every freshness/TTL/timestamp read sourced from `context.executed_at` and every truncation/availability read sourced from `context.effective_as_of`, nowhere else, in the analysis/resolver layer, with no remaining exception. |
| **IR.2.4 — Data-layer clock consolidation** | New `src/core/clock.py` (`utc_now()`); six decision-clock classes (`CachedHistoricalDataClient`, `financial/cache.py`, `financial/resolver.py`, `CachedInstrumentProfileResolver`, `SQLiteResolvedInputCache`, SEC EDGAR's provider) become required-clock, no default, fed from `context.executed_at` by every composition root — TTL/freshness decisions are judged against real elapsed time, never the requested historical boundary; SEC EDGAR's filing-eligibility check stops reusing the injected clock for that purpose and instead takes the boundary as an explicit argument fed `context.effective_as_of` as data (§6.11); nine event-timestamp files migrate their `datetime.now(UTC)`-defaulting pattern to `utc_now()` (§6.11's full table). The `datetime.now`/`utcnow`/`time.time` conformance check (§6.6 item 5) lands here, scanning all of `src/` with `src/core/clock.py` as the only exception, plus the named `logger_util.py` exemption pending confirmation (§6.11). | IR.2.3 (reuses its composition-root pattern; touches far more files, hence its own slice) | ...with every decision clock anywhere in the codebase sourced from `context.executed_at`, every truncation/eligibility decision sourced from `context.effective_as_of` passed as data, and every event timestamp sourced from one shared helper. |
| **IR.2.5 — Cache unification** | `context.use_cache` becomes the sole cache control for all four: `_production_financial_cache`'s `enabled` parameter removed; the durable cache is always wired at composition but opens storage lazily on first actual read/write, so `use_cache=False` never touches storage — matching today's behavior and avoiding a Step 3.3A readiness-check regression (§6.1 item 10, revised); Momentum's `BaseDataClient`/`MarketDataProvider`/`CachedHistoricalDataClient` gain a threaded `use_cache` parameter (§6.9's mechanism, steps 1–4), given the same lazy-open treatment for symmetry. This slice builds the *mechanism*; it does not yet add Momentum's `--no-cache` CLI surface — every composition root passes a fixed `use_cache=True` for Momentum until IR.2.6 wires a real toggle, which is a caller-surface gap, not an analyzer inconsistency (all four `run_analysis` bodies already consume `context.use_cache` identically at this point). | IR.2.1 (independent of 2.2/2.3/2.4 — either order works; listed after them to match the project owner's example ordering) | ...consuming `context.use_cache` identically, with the underlying data/cache-client layer able to honor it end-to-end without any storage-readiness regression. |
| **IR.2.6 — Momentum parity** | Everything that makes Momentum's *caller-facing surface* match the other three, not just its internals: `instrument_profile` embedded unconditionally in `MomentumRun` (orchestrator's `replace()` deleted, workspace reads the profile from the result, §6.4); real `--as-of`/`--no-cache` CLI options, `MomentumSelection.as_of`/`use_cache` fields, and `MomentumToolArguments.use_cache` (it already inherits `as_of`, §2 item 4); `MomentumAnalyzer.__init__` loses its `YFinanceClient()` default and `settings` reads (injected/required dependencies, §6.5); the TOML ticker-default fallback moves to the CLI; `MomentumPolicy` is deleted in favor of `MomentumConfig` (§2 item 4). Version bumps (§6.10) land here, since this is the slice that actually changes `MomentumSelection`'s and `MomentumRun`'s persisted shape. `MOMENTUM.md`'s retroactive-price-revision note (§6.9) lands here too. | IR.2.1, IR.2.3 (needs `effective_as_of` for `--as-of` to mean anything), IR.2.5 (needs the cache mechanism for `--no-cache` to mean anything) | ...at full parity: every field of `AnalysisContext` genuinely exercisable through every analyzer's real caller-facing surface, no placeholders, no known gaps. |

Each slice ends with the full managed gate and its own regression tests, per §4. IR.2 as a whole is
accepted only once all six sub-slices have landed and the conformance tests (§6.6) pass against the
final state.

### 6.13 IR.2.2 — Graham strategy separation (new sub-slice, project owner's direction 2026-09-25)

#### 6.13.1 Rationale

Graham Number and Graham Growth Value answer different questions with different formulas
(`MASTER_PLAN.md` principle 9: "The Graham Number and forecast-dependent Graham growth value are
separate methods"). They have shared a base (`_GrahamConfig`, `_GrahamSelection`,
`graham_contracts.py`) since before IR.2, and that base has caused two repeated partial fixes
already: §6.1 item 11 (Graham Growth's `fiscal_year` basis needed a method-specific carve-out the
shared base didn't have) and item 13 (the EPS-basis default diverged between the Config and
Selection entry points once both were forced through the same base method). The goal is not a
one-off fix but two equally good, standalone examples of how to implement a strategy — every field,
validator, and default a future strategy author copies from either package is that strategy's own,
never "because Graham shares it."

#### 6.13.2 File inventory — removed, new, and modified

**Removed:**

- `src/analysis/shared/graham_contracts.py` (`_GrahamConfig`, `_GrahamSelection`'s counterpart glue,
  `GrahamMethod`, `resolve_graham_eps_basis`, `GRAHAM_GROWTH_EXTRA_SEC_EDGAR_BASES`, `_require_ticker`,
  `_event`/`_trace_event`) — every symbol relocates per §6.13.3–6.13.4 or is duplicated locally
  where it is genuinely method-specific (each method's own accepted-basis set, its own bvps rule).
- `src/reporting/graham.py` — splits per §6.13.5.

**New:**

- `src/data/financial/eps_basis.py` — provider EPS-basis capability (§6.13.3).
- `src/reporting/valuation_presentation.py` — shared presentation primitives (§6.13.5).
- `src/reporting/graham_number.py`, `src/reporting/graham_growth.py` — method-specific presenters
  (§6.13.5).
- `docs/user/strategies/GRAHAM_NUMBER.md`, `docs/user/strategies/GRAHAM_GROWTH.md` (§6.13.8).

**Modified — each Graham method's own package absorbs what it used to borrow:**

| File | Change |
| :--- | :--- |
| `src/analysis/strategy/graham_number/config.py` | `GrahamNumberConfig` becomes a direct `BaseModel` subclass (drops `_GrahamConfig`), declaring `security_provider_id`/`quote_provider_id`/`eps_basis`/`eps_override`/`quote_override`/`bvps_override` itself, with its own `normalize_provider`/`normalize_basis` field validators (small, duplicated 1:1 from today's shared base — deliberate, not an oversight). `validate_method` calls the new `default_eps_basis_for_provider` (§6.13.3) and enforces Number's own accepted set (`{"three_year_average"}` for SEC EDGAR, `"ttm"` only for Massive — unchanged from today) plus the existing bvps-for-Massive rule. `GrahamNumberEPSBasis` stays defined here (already is). |
| `src/analysis/strategy/graham_growth/config.py` | Same pattern; `GrahamGrowthConfig`'s own accepted SEC EDGAR set is `{"three_year_average", "fiscal_year"}` (unchanged). `GrahamGrowthEPSBasis` stays defined here. |
| `src/analysis/strategy/graham_number/calculation.py` | `GrahamNumberInputAssembly`/`GrahamNumberResult`'s `method` field becomes `Literal["graham_number"]` (was `GrahamMethod.NUMBER`) — no enum, no shared type. `_trace_event` calls become the new neutral `single_event_trace` (§6.13.4). Its own defense-in-depth `eps_basis not in ("three_year_average", "ttm")` resolver-layer check is untouched (already Number-only, never shared with Growth). |
| `src/analysis/strategy/graham_growth/calculation.py` | Same pattern; `method` becomes `Literal["graham_growth_value"]`. |
| `src/analysis/strategy/graham_number/analyzer.py` | `_require_ticker` import repoints to the new neutral home (§6.13.4); everything else unchanged from IR.2.1. |
| `src/analysis/strategy/graham_growth/analyzer.py` | Same. |
| `src/workspace/requests.py` | `GrahamNumberSelection`/`GrahamGrowthSelection` each subclass `_FrozenSelection` directly (the already-neutral strictness mixin every selection type uses, including Momentum/FCF — not Graham-specific, stays). No more `_GrahamSelection` intermediate: each declares its own `security_provider_id`/`quote_provider_id`/`eps_basis`/`eps_override`/`quote_override`/`as_of`/`use_cache` fields and field validators. Each's `analysis_id` becomes its own value (§6.13.6) instead of the shared `"graham"`. Each `model_validator(mode="after")` **validates by constructing its own Config** (`self.to_graham_number_config()` / `self.to_graham_growth_config()`, called on the *raw*, not-yet-resolved field values, exactly the two methods already used to convert a finished Selection to a Config) and reads the resolved `eps_basis`/`quote_provider_id` back from the constructed Config, propagating a `ValueError` on rejection. This makes each `*Config`'s `validate_method` the single, sole implementation of that method's entire acceptance rule — Config's bvps-for-Massive check runs for free too, so `GrahamNumberSelection`'s separate `_require_massive_book_value` validator is deleted as redundant, closing the same two-entry-point-divergence risk found in item 13 for the bvps rule as well, not just EPS basis. This "validate by constructing its config" pattern only imports each strategy's `Config` *class* (already imported for `to_*_config()`), so it does not cross the strategy boundary with a plain-function import (§6.6 item 4 stays satisfied). |
| `src/orchestrator/analysis_tools.py` | `GrahamNumberEPSBasis`/`GrahamGrowthEPSBasis` imports repoint to each strategy's own `config.py` instead of `graham_contracts.py`. No other change — the tool-argument classes were already fully separate (§6.13's file inventory found no other Graham-shared code here). |
| `src/workspace/graham_number.py`, `src/workspace/graham_growth.py` | Codec `method` comparisons change from `GrahamMethod.NUMBER`/`GrahamMethod.GROWTH_VALUE` to the plain string literals `"graham_number"`/`"graham_growth_value"` (matching the JSON wire format they already compare against in `decode_*`). No `GrahamMethod` import. |
| `src/cli.py` | Import paths only (`GrahamNumberEPSBasis`/`GrahamGrowthEPSBasis`, presenter functions from the two new reporting modules instead of `reporting.graham`); `execution_errors(analysis="graham", ...)` becomes `analysis="graham_number"`/`analysis="graham_growth_value"` per command (four call sites, §6.13.6). |

#### 6.13.3 Provider EPS-basis capability (data layer) and the item 13 fix

New `src/data/financial/eps_basis.py`:

```python
"""Provider EPS-basis capability, shared by every strategy that resolves normalized EPS."""

from typing import Final

from src.data.financial.providers import MASSIVE_PROVIDER_ID, SEC_PROVIDER_ID

MASSIVE_ONLY_EPS_BASIS: Final = "ttm"


def default_eps_basis_for_provider(provider_id: str) -> str:
    """Return the provider-driven default EPS basis.

    SEC EDGAR defaults to three-year-average; every other provider — including Massive,
    which can structurally only ever supply TTM — defaults to TTM. Every strategy calls
    this same function for its own default, so a provider's own default can never be
    rejected by that same provider's own accept rule (the bug behind §6.1 item 13).
    """
    return "three_year_average" if provider_id == SEC_PROVIDER_ID else MASSIVE_ONLY_EPS_BASIS


def is_massive_provider(provider_id: str) -> bool:
    """Return whether *provider_id* is Massive, which supplies EPS as TTM only."""
    return provider_id == MASSIVE_PROVIDER_ID
```

`SEC_PROVIDER_ID`/`MASSIVE_PROVIDER_ID` import from the already-existing neutral re-export point
`src.data.financial.providers` (not the provider-specific submodules directly, which would create
an import cycle back through `src/data/sec_edgar/financial_facts.py`, itself an importer of
`src/data/financial/**`).

**What stays strategy-owned, deliberately:** each method's *accepted* SEC EDGAR basis set is
strategy policy, not a data-layer capability — SEC EDGAR can structurally supply more bases than
either method today chooses to accept (neither accepts an explicit `"ttm"` with SEC EDGAR, matching
current behavior exactly), so there is no "provider capability ∩ strategy policy" intersection to
compute; `default_eps_basis_for_provider` is the only piece both methods share, and it is a data
fact (which basis a provider's default query supplies), not a business rule. **This design changes
no accept/reject outcome for any known provider — only the default computation, unifying it into
one provider-driven rule applied by both methods at both of their entry points**, exactly satisfying
the project owner's item 13 direction. `GrahamNumberConfig`/`GrahamGrowthConfig` each keep their own
hardcoded accepted-set check (`{"three_year_average"}` / `{"three_year_average", "fiscal_year"}` for
SEC EDGAR; `is_massive_provider(...)` + `MASSIVE_ONLY_EPS_BASIS` for Massive) — this is intentional,
approved strategy-specific policy per `docs/user/GRAHAM_NUMBER.md`/`GRAHAM_GROWTH.md`, not
duplication of the same rule.

Permissiveness for injected/synthetic provider ids (dependency injection, test fixtures) is
preserved exactly as today: the accepted-set checks only fire `if security_provider_id ==
SEC_PROVIDER_ID` or `is_massive_provider(...)`; anything else — including every fixture provider id
used across the existing test suite — is unrestricted, and `default_eps_basis_for_provider` still
returns a concrete default (`"ttm"`, via the same `else` branch Massive uses) for any unrecognized
id, matching the Selection-path behavior already exercised by
`tests/workspace/test_requests.py::test_graham_snapshot_is_independent_of_caller_inputs` today
(this also resolves that test's underlying finding from §6.1 item 13 — Graham Number's Config path
now defaults the same way Selection already does, so the two entry points agree).

#### 6.13.4 Neutral homes for genuinely general behavior

- **Quote resolution and the price-relationship comparison already live in the neutral
  `src/analysis/shared/financial_resolution.py`** (`resolve_optional_quote`,
  `evaluate_price_comparison`/`PriceComparison`, `resolve_normalized_eps`, `margin_of_safety`,
  `common_currency`, `validate_profile_ticker`, `is_known_etf`, `has_provider_backed_evidence`) —
  confirmed by direct inspection; no move needed, and this module is the intended home for the same
  primitives once NCAV/EPV/reverse-DCF need them, per the project owner's direction.
- **`_event`/`_trace_event`** (construct a one-event `ResolutionTrace` from a message) move into
  `src/data/financial/resolution_trace.py` as a public `single_event_trace(field_name, stage,
  outcome, message) -> ResolutionTrace` module-level function — genuinely general resolution-trace
  infrastructure, not Graham-specific, and it already sits next to `ResolutionEvent`/`ResolutionTrace`
  themselves.
- **`_require_ticker`** (strip/upper/require-nonblank) moves into `financial_resolution.py` as a
  public `require_ticker(ticker: str) -> str` — it is fully generic today in everything but its
  current location; FCF's analyzer already duplicates the identical `ticker.strip().upper()` logic
  inline rather than importing it, which this move makes available to fix later, but adopting it in
  FCF/Momentum is out of this sub-slice's scope (not requested, and not a Graham-shared-base
  problem) and is left as-is.

#### 6.13.5 Reporting split

`src/reporting/graham.py` (1,224 lines) splits three ways. Functions already prefixed `_number_*`/
`_growth_*`, both `*Presentation` dataclasses, and both `render_graham_*` functions move verbatim
into `reporting/graham_number.py`/`reporting/graham_growth.py` respectively. The remaining
functions — every one operating only on generic types (`PriceComparison`, `ResolvedInput`,
`CalculationStatus`, `InstrumentProfile`, `SecurityIdentityResolution`, `ResolutionTrace`) with no
Graham-specific parameter — move into new `reporting/valuation_presentation.py`:
`public_quote_reason`, `friendly_graham_failure` (renamed `friendly_valuation_failure`, wording
genericized from "the requested Graham inputs" to "the requested inputs" — a presentation-text
change, not a calculation change), `_analysis_heading`, `_result_heading`, `_status_label`,
`_effective_status_and_reason`, `_identity_detail_lines`, `_identity_diagnostic_lines`,
`_kind_detail_lines`, `_profile_diagnostic_lines`, `_profile_diagnostic_payloads`,
`_input_detail_lines`, `_diagnostic_lines`, `_investor_comparison_evidence`, `_comparison_reason`,
`_comparison_payload`, `_comparison_details`, `_comparison_lines`, `_override_warnings`,
`_quote_warnings`, `_source_summary`, `_display_basis`, `_freshness_label`, `_source_label`,
`_resolved_input_payload`, `_eps_basis_label`, `_uses_diluted_eps` (both strategies present an EPS
basis, so these two are genuinely shared, unlike `_bvps_basis_label`/`_number_basis_summary`, which
stay Number-only), `_trace_payload`, `_quote_payload`, `_common_currency`,
`_validate_presentation_as_of`, `_validate_ticker`, `_validate_margin`, `_json_datetime`,
`basis_display_name`, `field_display_name`, `units_display_name` (the lookup *functions* are
generic; each strategy's reporting module keeps its **own** complete `BASIS_DISPLAY_NAMES`/
`FIELD_DISPLAY_NAMES`/`UNITS_DISPLAY_NAMES` dict rather than merging a shared partial one — a
handful of display-label strings like `"TTM"` appearing in both dicts is inert duplication of a
presentation label, not the validation-logic duplication risk items 11/13 were about, so it is not
worth a merge mechanism).

#### 6.13.6 Persistence, `analysis_id`, and version bumps

Per the project owner's direction: each method gets its own `analysis_id` — `graham_number` and
`graham_growth_value` — matching each one's existing, unchanged `method_id`. This is the expected
shape for a single-method analysis family (compare Momentum's `analysis_id="momentum"`/
`method_id="sma_crossover"` and FCF's `analysis_id="fcf_earnings_growth"`/
`method_id="reported_fcf_eps_cagr"`, where the family and its one current method are still named
distinctly because a future variant is plausible there too; Graham Number and Graham Growth Value
are not variants of one calculation the way, e.g., Altman Z and Z′′ would be — they already are, and
remain, two unrelated formulas, so collapsing analysis_id onto method_id here is the correct
instance of "one analysis, one method," not a special case). Concretely: `GrahamNumberSelection.analysis_id:
Literal["graham_number"] = "graham_number"`, `GrahamGrowthSelection.analysis_id:
Literal["graham_growth_value"] = "graham_growth_value"`, `config_schema_version` bumped per
`AGENTS.md` §0 (no migration; stored data has no compatibility value during this consolidation
period, §6.10). Every literal `"analysis": "graham"` / `analysis_id="graham"` / `analysis="graham"`
site found across production code (`reporting/graham.py`'s two JSON payload builders, `cli.py`'s
four `execution_errors(analysis="graham", ...)` call sites) and tests (enumerated by direct
inspection: `tests/data/repositories/test_schema.py`, `tests/reporting/test_analysis_run_replay.py`,
`tests/test_cli.py`, `tests/workspace/test_requests.py`, `tests/workspace/test_runs.py`, plus
`tests/workspace/test_fcf_growth_codec.py:298`'s `("strategy_id", "graham")` case, to be verified
during implementation rather than assumed) is updated to the method-specific value. Orchestrator
tool names (`analyze_graham_number`, `analyze_graham_growth_value`) are unrelated and unchanged —
they were already method-specific.

#### 6.13.7 Evaluation harness: `graham_method_selection` folds into ordinary strategy-selection

`src/evaluation/models.py` defines its own, entirely separate `GrahamMethod` enum (tool-call
constraint vocabulary: `GRAHAM_NUMBER`/`GRAHAM_GROWTH_VALUE`) and a distinct
`EvaluationCategory.GRAHAM_METHOD_SELECTION` metric, evaluated by
`evaluate_graham_method_selection()` in `evaluator.py` and consumed by both `runner.py` and
`ollama_runner.py` — unrelated to the analysis-layer `GrahamMethod` being removed, and **not**
itself part of this sub-slice's "no shared Graham code" scope (it is evaluation-harness
infrastructure, not a shared analyzer base). It exists to check that the correct Graham *method* was
selected as distinct from the correct *tool* — a distinction that stops mattering once Graham Number
and Graham Growth Value are ordinary, independent tools like Momentum and FCF Growth, each already
covered by ordinary strategy-/tool-selection evaluation. Per the project owner's direction ("update
the milestone exit criteria's 'Graham method-selection' metric to ordinary tool selection"):
`evaluate_graham_method_selection` and `EvaluationCategory.GRAHAM_METHOD_SELECTION` are removed:
existing Golden cases that supplied `graham_method_constraints` express that same constraint through
ordinary tool-selection expectations instead (the two are checking the same fact — which tool/method
handled the request — once Graham Number and Graham Growth Value are separate tools). Touches
`src/evaluation/models.py`, `src/evaluation/evaluator.py`, `src/evaluation/runner.py`,
`src/evaluation/ollama_runner.py`, and their test files
(`tests/evaluation/test_evaluator.py`, `tests/evaluation/test_models.py`), plus
`docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md:368`'s exit-criteria sentence, which drops
"Graham method-selection" from its own reported category alongside "strategy-selection."

#### 6.13.8 Docs split

`docs/user/strategies/GRAHAM.md` splits into `GRAHAM_NUMBER.md` and `GRAHAM_GROWTH.md`, each keeping
its method's own sections (method mechanics, earnings basis, applicability, required inputs) plus
the sections both need duplicated in full (presentation modes, data sources, point-in-time analysis,
"why another Graham calculator may disagree," limitations) — full independence over a shared
reference, matching the code split. `GRAHAM.md` itself becomes a short overview (what Graham
valuation is, one paragraph each on Number vs Growth Value, links to both full guides) rather than
being deleted, so existing inbound links keep resolving. `docs/project/ARCHITECTURE.md`'s Graham
description (currently: "`shared/graham_contracts.py` holds common Graham configuration and method
contracts") and its file-tree listing of `graham_contracts.py` are updated to describe two
independent packages instead.

#### 6.13.9 Test impact and the no-formula-change guarantee

No formula, classification, or result change anywhere in this sub-slice — every `compute_graham_number`/
`compute_graham_growth_value` calculation body is untouched, and every Golden-suite case must pass
with the same numeric/classification outcome, checked and reported per case before this sub-slice is
considered complete (matching the standard this project already applied to item 11's eps_basis fix
and IR.2.1's ticker-normalization/CLI-permissiveness findings — verify, don't assume, and report any
newly-affected case rather than retuning it to force a pass). Expected test-file touch points, beyond
those already named in §6.13.6/6.13.7: `tests/analysis/graham_value/test_analyzer_config.py`,
`test_method_analyzers.py` (import path updates to the two new config modules; `_config`/`_context`
helpers unaffected in shape), `tests/workspace/test_requests.py` (removal of `_GrahamSelection`-level
shared tests, replaced by each Selection's own), `tests/reporting/` Graham presentation tests split
to match the new module boundaries, and `tests/analysis/test_base_analyzer_conformance.py` — item 4's
AST-based strategy-boundary scan should be re-run explicitly as part of this sub-slice's gate, since
it is the test most directly designed to catch exactly the kind of cross-boundary coupling this
sub-slice removes.
