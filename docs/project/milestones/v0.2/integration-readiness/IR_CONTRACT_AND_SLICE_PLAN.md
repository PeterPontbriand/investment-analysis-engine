# IR — Integration Readiness: Contract and Slice Plan

Makes the four existing analyses safely consumable by an external harness (a backtester, optimizer,
or other automated consumer) without turning this project into that harness.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **The role this project plays for an external consumer:** a point-in-time evidence and filter
  provider ("only allow a signal in an equity where Graham passes and Momentum is bullish as of
  date T"), not a trading-signal or order-generation system. This matches the existing design:
  Graham Number is a screening ceiling, Graham Growth a forecast-dependent estimate, and Momentum a
  regime label. None of them is an entry/exit rule.
- **What this work package does:** makes that existing role safer to consume. One invocation shape
  and one meaning for time and caching across all four analyses, installs that work on every
  declared Python version, a complete watchlist lifecycle for agentic CLI callers, and architecture
  documentation a contributor can trust.
- **What it does not do:** add trading logic, backtesting infrastructure, a new strategy shape, or
  an actual harness adapter. Full list: [Out of scope](#4-out-of-scope).
- **Rules every slice follows:** no formula or classification changes (a suspected calculation
  error is reported, not fixed here); the managed quality gate after every slice; explicit
  authorization before the next slice begins.
- **Where the history lives:** why this work package exists is in
  [Background](#6-background-origin-of-this-work-package); renumbering, branching and other decision
  records are in [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Each slice ends with the managed quality gate and is gated by explicit authorization before the
next begins. The one exception is a slice whose entire diff is non-executable declarative metadata
with no import-time or runtime effect (IR.1), where confirming the file still parses is sufficient;
see `docs/project/README.md`'s Quality gates section for the exact boundary.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| IR.1 | [License declaration fix](#ir1--license-declaration) | Complete | 2026-09-24 |
| IR.4 | [Python-version reproducibility](IR4_PYTHON_VERSION_REPRODUCIBILITY.md) | Complete | 2026-09-26 |
| IR.7 | [`ARCHITECTURE.md` contributor pass](IR7_ARCHITECTURE_DOC_CONTRIBUTOR_PASS.md) | Complete | 2026-09-27 |
| IR.2 | [Analyzer envelope unification and Momentum parity](IR2_ANALYZER_ENVELOPE_PLAN.md) | Complete | 2026-09-29 |
| IR.8 | [Windows path anchoring guard](IR8_WINDOWS_PATH_ANCHORING_GUARD.md) | Complete | 2026-09-30 |
| IR.6 | [Watchlist lifecycle completion](IR6_WATCHLIST_LIFECYCLE_COMPLETION.md) | Complete | 2026-09-30 |

`feat/ir-integration-readiness` is retired once PR #48 merges; all remaining IR work branches from `main`.

## 3. The slices

### IR.1 — License declaration

- **Problem:** `LICENSE` is Apache-2.0, but `pyproject.toml` declared `license = {text = "MIT"}`.
- **Decision:** standardize on Apache-2.0, changing `pyproject.toml` to match `LICENSE`. This was a
  licensing decision, authorized explicitly by the project owner on 2026-09-23.
- **Also fixed in IR.1:** `momentum_analyzer.py` failed to import on Python 3.12/3.13 because of an
  eagerly evaluated `pd.Series[float]` annotation
  ([record](#a1-ir1-found-and-fixed-momentum_analyzerpy-import-failure-on-python-312313)).
- **Landed separately, ahead of IR.1:** a self-contradiction in `MOMENTUM.md` about RSI
  ([record](#a2-momentummd-rsi-self-contradiction)).

### IR.2 — Analyzer envelope unification and Momentum parity

- **Goal:** every strategy subclasses `BaseAnalyzer[ConfigT, ResultT]` and is invoked the same way,
  `run_analysis(ticker, config, context)`.
- **The shared context:** `AnalysisContext` carries `as_of`, `executed_at`, `use_cache` and
  `instrument_profile`, each with one meaning read identically by all four analyzers.
  `effective_as_of` is derived from `as_of` and `executed_at`.
- **Dependencies are injected and required:** no analyzer constructs its own client, reads
  `src.config.settings`, or reads an uninjected clock.
- **No new framework:** no generic result supertype, registry or factory. Each strategy keeps its own
  `ConfigT` and `ResultT`.
- **Momentum reaches full parity** with the other three: real `--as-of` and `--no-cache`, an
  embedded instrument profile, injected dependencies, and a pure calculation function.
- **Persisted shapes may change** during this consolidation period (`AGENTS.md` §0): version fields
  bump, with no migration or compatibility code for stored data.
- **Delivered in six gated sub-slices**, split by concern rather than by analyzer, all on
  `feat/ir-integration-readiness`. Nothing merges to `main` until the last sub-slice is accepted.
- **Verification:** Step 3.5's Piotroski analyzer, the first analyzer built from scratch against this
  envelope, is its test. Any envelope change Piotroski needs is applied to all five analyzers, not
  accepted as a special case.
- **Detail:** [IR.2 plan](IR2_ANALYZER_ENVELOPE_PLAN.md), which holds the sub-slice sequence table,
  the full call-site and field inventory, and every design decision.

### IR.4 — Python-version reproducibility

- **Problem:** `requires-python = ">=3.12"` was not honored on 3.12/3.13. `market_data.py`'s eagerly
  evaluated `pd.Index[Any]` annotations failed at import time, and CI tested only 3.14, so the
  failure had never been exercised.
- **Delivered** on its own branch off `main`, merged to `main` independently, then merged back into
  `feat/ir-integration-readiness` (branching rationale: [A.5](#a5-branching-decisions)).
- **Detail and completion record:** [IR4_PYTHON_VERSION_REPRODUCIBILITY.md](IR4_PYTHON_VERSION_REPRODUCIBILITY.md).

### IR.6 — Watchlist lifecycle completion

- **Problem:** an agentic caller driving `ian` through its CLI can create a watchlist but never
  remove it, and must use two vocabularies to name the same method.
- **Scope, in three gated sub-slices:** IR.6.1 command vocabulary (`remove-ticker`/`remove-method`,
  `runs list --analysis`, alias-only text output), IR.6.2 `watchlist delete`, IR.6.3
  `watchlist rename`. No schema change or migration.
- **Branch:** its own, off `main` after `feat/ir-integration-readiness` has merged; IR.2.6 changed the
  watchlist removal commands and text IR.6.1 rewrites, so IR.6 depends on IR.2.
- **Detail and completion record:** [IR6_WATCHLIST_LIFECYCLE_COMPLETION.md](IR6_WATCHLIST_LIFECYCLE_COMPLETION.md).
  Complete pending the project owner's acceptance.

### IR.7 — `ARCHITECTURE.md` contributor pass

- **Scope:** reorganize `ARCHITECTURE.md` for a first-time contributor, remove stale labels and
  contradictions, and add a repo-wide Markdown link and anchor checker
  (`scripts/check_doc_links.py`) to the quality gate.
- **Branch:** its own, off `feat/ir-integration-readiness` (not `main`), merged back into it.
- **Detail and completion record:** [IR7_ARCHITECTURE_DOC_CONTRIBUTOR_PASS.md](IR7_ARCHITECTURE_DOC_CONTRIBUTOR_PASS.md).

### IR.8 — Windows path anchoring guard

- **Problem:** on Windows, a path that is only partly anchored (`/e/Source/x`, how Git Bash writes
  paths, or `E:data`) is accepted silently and resolves against the current drive, so SQLite or the
  log handlers create folders outside the project.
- **Decision:** reject such a path, with a message that names the setting and suggests the full path,
  in the settings loader and in `evaluate --report`; show the reason in the `db` commands. No automatic
  conversion, and no change on Linux or macOS.
- **Scope:** `src/utils/paths.py`, `src/config.py`, `src/cli_database.py`, `src/cli.py` (`evaluate`),
  `docs/user/DATABASE.md`, `AGENTS.md`, and tests. Relative `log_dir` and `telemetry_log_dir` now resolve
  under the project folder.
- **Branch:** `fix/ir8-windows-path-guard`, off `main`, merged to `main` on its own.
- **Detail and completion record:** [IR8_WINDOWS_PATH_ANCHORING_GUARD.md](IR8_WINDOWS_PATH_ANCHORING_GUARD.md).
  Complete pending the project owner's acceptance.

### Moved out: typed JSON envelopes (formerly IR.5)

Typed JSON envelope models and generated JSON Schemas for `--json` payloads moved to the
[strategy wiring consolidation work package (SWC)](../STRATEGY_WIRING_CONSOLIDATION_PROPOSAL.md)
on 2026-09-24. They are per-strategy wiring of the same kind SWC consolidates, so building them on
SWC's shared strategy descriptor means writing them once instead of once per strategy. Details:
[A.4](#a4-slice-numbering-history).

### Moved out: Momentum series API (formerly IR.3)

A pure, vectorized Momentum series API (full SMA short/long, RSI and crossover series beneath the
snapshot API) moved to the [evidence-provider candidate backlog](../../../EVIDENCE_PROVIDER_ROADMAP.md)
on 2026-09-30. No consumer needs per-bar evaluation: the external backtester integration that
motivated it was judged not viable ([Background](#6-background-origin-of-this-work-package)), and
point-in-time filtering is already served by `--as-of` on every caller surface. The backlog row
carries the original scope, the trigger to revisit it and the questions a future plan must answer.
The IR.3 number is retired, not reused. Details: [A.4](#a4-slice-numbering-history).

## 4. Out of scope

- Any new trading-signal, entry/exit, or order-generation capability.
- A `compute_series`-style API for any analysis. Momentum's is a candidate in the
  [backlog](../../../EVIDENCE_PROVIDER_ROADMAP.md); the three fundamentals-based analyses evaluate
  once per fiscal period, not once per bar, so a per-bar series API would be speculative for them.
- An actual MCP server, subprocess boundary, or harness adapter. This work package makes that
  possible later; it doesn't build it.
- Backtester-specific integration code for any named external project.
- Changing any analysis's existing formulas, classifications, or presentation contracts beyond what's
  needed to fix the specific defects in scope.
- The `src` → real package rename, which is its own work package (`PKG`, see the milestone plan's
  sequence table) because of its scale.

## 5. Acceptance criteria

- **No formula or classification change.** A calculation believed incorrect during IR is reported to
  the project owner, not silently corrected here; that goes through the existing-strategy-correctness
  process. Exit codes and presentation *output* (what the CLI or orchestrator caller actually sees)
  don't change. The *internal* config and context shapes and persisted evidence/config schemas that
  produce that output may, per `AGENTS.md` §0: version fields bump accordingly, with no migration or
  compatibility code for stored data during this consolidation period. Two exceptions to the
  presentation-output rule were explicitly accepted:
  [A.3](#a3-accepted-exceptions-to-the-presentation-output-rule).
- **Quality gate:** the complete managed gate (`scripts/run-quality-gates.ps1` / `.sh`), ≥85%
  coverage, after every slice that touches Python source, tests, or executable configuration. IR.1 is
  exempt, per the sequencing note in [§2](#2-sequence-and-status).
- **Regression tests:** each slice's own tests cover the specific defect it fixes. IR.2 also adds the
  structural conformance tests described in its plan.
- **Acceptance record:** a final record analogous to this project's other work-package acceptance
  records. For IR.2 specifically, it notes which persisted-shape version fields changed and confirms
  no Alembic migration was required.
- **ESC re-run before Step 3.5:** the full Existing Strategy Correctness audit matrix re-runs once,
  after IR as a whole is complete, to confirm no analysis result changed across the whole work
  package. Once at the end, not slice by slice, per the project owner's direction. The re-run is
  [ESC-E](../existing-strategy-correctness/ESC_E_RENEWAL_PLAN.md).

## 6. Background: origin of this work package

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

**Relationship to the candidate backlog:** a later, separately drafted
[candidate backlog](../../../EVIDENCE_PROVIDER_ROADMAP.md) drew on the same originating review and
surfaced overlapping "library-readiness" observations, not an independent conclusion; where its
scope duplicated this document's, this document remains the authoritative source and the backlog
defers to it.

---

## Appendix A: Decision records and history

Kept for the record. Nothing here is needed to understand what IR does or what comes next.

Commit IDs cited in the IR planning records up to IR.2's acceptance are `feat/ir-integration-readiness`'s
individual commits, preserved on GitHub under PR #48 (`git fetch origin pull/48/head`), not in
`main`'s history, because that PR is squash-merged.

### A.1 IR.1: found and fixed `momentum_analyzer.py` import failure on Python 3.12/3.13

`pyproject.toml` declares `requires-python = ">=3.12"`, but
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

The same defect class later turned up in `src/data/repositories/market_data.py`, which this audit
(scoped to `src/analysis/strategy/*/*.py`) missed; that became IR.4.

### A.2 `MOMENTUM.md` RSI self-contradiction

Line 44 documented the simple-average RSI convention while line 118 listed RSI among indicators
"not currently implemented." Fixed directly (a user-facing documentation correction, not a planning
change) rather than waiting for IR.1's implementation slice, since the actual and
correctly-documented behavior in `FINANCE_MATH.md` and `GLOSSARY.md` was never in question. IR.1
accordingly consists only of the license fix.

### A.3 Accepted exceptions to the presentation-output rule

**Accepted exception (IR.2.2, 2026-09-25):** `friendly_graham_failure`'s renaming to
`friendly_valuation_failure` (IR.2 plan §6.13.5 — the function generalizes as it moves to the neutral
`evidence_presentation.py` module, ahead of NCAV/EPV/reverse-DCF strategies needing the same
failure-prose helper) changed its wording from "the requested Graham inputs are invalid" to "the
requested inputs are invalid." This is an investor-facing presentation-output wording change, not
a formula, classification, or exit-code change — the failure is still reported under the exact
same conditions, with the exact same status and exit code, just described without a now-inaccurate
strategy name once the function is no longer Graham-specific. Recorded here rather than silently
allowed, per this criterion's own "do not change" rule; every affected test assertion was updated
to match, not left passing by coincidence.

**Accepted exception (IR.6.1, approved 2026-09-27):** the workspace commands' human-readable
text (`watchlist show`, `runs list`, `refresh`) shows the hyphenated analysis aliases where it
printed canonical `method_id`s, and the `watchlist remove`/`disable` commands and `runs list
--method` are replaced by `remove-ticker`/`remove-method` and `runs list --analysis`. This is
a workspace command-surface change, not an analysis formula, classification, result, or exit-code
change. Every `--json` payload, including its canonical `method_id`, is unchanged.

### A.4 Slice numbering history

- **IR.3 (Momentum purity) folded into IR.2, 2026-09-24.** Momentum's quality-check and clock purity,
  `MomentumPolicy`'s deletion, real `as_of`/`use_cache`, and injected dependencies became part of
  IR.2, since "one meaning per context field, all four analyzers" is inseparable from Momentum's own
  reshaping.
- **Momentum series API renumbered IR.4 → IR.3.** Renumbered from IR.4 to IR.3 now that the slice
  between it and IR.2 (previously IR.3, Momentum purity) no longer exists as a separate slice. The
  freed "IR.4" label is reused below for an unrelated slice; that is not this content returning.
- **IR.5 moved to SWC, 2026-09-24.** Typed JSON envelope models and generated JSON Schemas for
  `--json` payloads (previously item 7 / slice IR.5) are per-strategy wiring in the same shape as
  everything else `SWC`'s proposal (`../STRATEGY_WIRING_CONSOLIDATION_PROPOSAL.md`) catalogs: one
  hand-written builder per strategy today, about to become five more with Step 3.5. Building it on
  `SWC`'s shared strategy descriptor means writing it once, not four (soon nine) times by hand. The
  substance of the original scoping — real typed envelope models backing the payload builders, not a
  snapshot generated once from whatever happens to exist, published to a checked-in `schemas/`
  directory — carries forward unchanged into `SWC`'s own eventual contract; only the work package
  that owns it changed. Its two open questions (schema-generation approach; the checked-in `schemas/`
  directory) travel with it and will be settled in SWC's own contract.
- **IR.4 reused for Python-version reproducibility, 2026-09-25.** Labeled IR.4, reusing the number
  freed when the old IR.4 (Momentum series API) was renumbered to IR.3 — an unrelated new slice found
  during IR.2.3 verification, not a revival of that content.
- **Momentum series API moved to the candidate backlog, 2026-09-30.** The project owner decided that
  no consumer needs per-bar evaluation (the external backtester integration was judged not viable, and
  `--as-of` already serves point-in-time filtering), so the slice left IR and became a candidate in
  [`EVIDENCE_PROVIDER_ROADMAP.md`](../../../EVIDENCE_PROVIDER_ROADMAP.md). The IR.3 number is retired,
  not reused, so it cannot be confused with either earlier IR.3 (Momentum purity, or the series API
  under its renumbered label).
- **IR.6 added, 2026-09-27.** Labeled IR.6, not IR.5, because "IR.5" still labels the JSON-envelope
  scope that moved to `SWC`.
- **IR.7 added, 2026-09-27.** Found and required by the `docs/contributor-documentation` merge
  review, not a pre-existing scope item.

### A.5 Branching decisions

**IR.4:** Branch: its own (`fix/ir4-python-version-reproducibility` off `main`, not
`feat/ir-integration-readiness`), merged to `main` independently once accepted — decided, not left
open. IR.2's sub-slices all land on one branch with nothing merging to `main` until the last is
accepted; binding IR.4 to that same rule would leave a verified-broken `requires-python` claim on
`main` for as long as IR.2.4–IR.2.6 take, for a defect with no dependency on any of them. After IR.4
merges to `main`, `feat/ir-integration-readiness` merges `main` back in before IR.2.4 begins, so
IR.2's remaining sub-slices are gated by a genuinely working 3.12/3.13 CI too, not developed against
the same 3.14-only blind spot that hid this defect.

**IR.6:** Branch: its own (`fix/ir6-watchlist-lifecycle` off `main`), merged to `main` independently
once accepted, following IR.4's precedent; `feat/ir-integration-readiness` merges `main` back in
afterward. **Revised 2026-09-29:** IR.2.6 changed the watchlist removal commands, their error handling
and their confirmation text, which IR.6.1 rewrites, so IR.6 now branches off `main` after
`feat/ir-integration-readiness` has merged.

**IR.7:** Branch: its own (`fix/ir7-architecture-doc-pass` off `feat/ir-integration-readiness`, not
`main`, since `main`'s `ARCHITECTURE.md` predates IR.2.1–2.4 and would recreate the collision the
`docs/contributor-documentation` merge resolved), merging back into `feat/ir-integration-readiness`
directly.

### A.6 Milestone-plan status history

Moved here from `IMPLEMENTATION_PLAN.md`'s row 10, which now carries only status and date.

Reordered ahead of R3 (2026-09-24) — IR.2 itself removes a verified set of dead code as an
intrinsic consequence of unifying the analyzer envelope, so R3's general sweep runs against an
already-smaller, already-cleaned codebase instead of duplicating IR.2's reachability analysis.
IR.1, IR.2, and IR.3 (renumbered from IR.4) remain in this work package; the old IR.3 (Momentum
purity) folded into IR.2 (2026-09-24); IR.5 moved to SWC. IR.4 (Python-version reproducibility,
reusing the number freed by IR.3's renumbering) was delivered independently on its own branch and
merged back 2026-09-26; its spec and completion record live in
[IR4_PYTHON_VERSION_REPRODUCIBILITY.md](IR4_PYTHON_VERSION_REPRODUCIBILITY.md). IR.6 (watchlist
lifecycle completion: delete, rename, one method vocabulary), added 2026-09-27, is planned on its
own branch off `main` like IR.4; see
[IR6_WATCHLIST_LIFECYCLE_COMPLETION.md](IR6_WATCHLIST_LIFECYCLE_COMPLETION.md).

The Momentum series API (the renumbered IR.3 named above) moved to the candidate backlog on
2026-09-30; see [A.4](#a4-slice-numbering-history).
