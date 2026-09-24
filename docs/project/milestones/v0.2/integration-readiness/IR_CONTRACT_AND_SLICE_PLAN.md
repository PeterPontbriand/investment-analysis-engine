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
3. **Unify the analyzer return contract.** `BaseAnalyzer.run_analysis` is typed to return `Any`;
   `FCFEarningsGrowthAnalyzer` does not subclass `BaseAnalyzer` at all, unlike the other three
   analyzers. Give the base a real generic return type and bring FCF's analyzer under it,
   preserving every existing call site's actual behavior — this is a typing/inheritance
   correction, not a behavior change. Per `AGENTS.md` §3, this stays a typed-result correction, not
   a generic result supertype, registry, or factory. IR.2 ships and lands on the four existing
   analyzers; its contract is not fully proven until a genuinely new analyzer is built against it,
   so Step 3.5's Piotroski F-Score implementation
   (`docs/project/milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md` §2.1) — the first
   Step 3.5 analyzer, landing after IR — should confirm or revise the contract as its own first
   real-world check, rather than IR.2 being treated as the last word on it.
4. **Momentum calculation purity.** `MomentumAnalyzer.run_analysis` calls `datetime.now(UTC)`
   twice (once for its internal quality-context clock, once for the result timestamp) and opens
   a logger on every call, none of it injectable. Its internal quality re-check also ignores any
   `as_of` boundary and duplicates a check `MomentumInputResolver.resolve()` already performed
   (with a real injected clock and `as_of` awareness) when called via `run_with_context`.
   **Decided:** `run_analysis`'s own check becomes independently clock-injected and
   `as_of`-aware too, rather than trusting the resolver's earlier check — this is deliberate
   defense in depth (verify at both the resolution boundary and the calculation boundary,
   never assume an upstream check was sufficient), consistent with a trust-but-verify approach
   to this project generally. This means the direct/preloaded-frame `df=` API (which never goes
   through the resolver, and so has no earlier check to rely on) keeps its own independent guard
   for free. Verify this also closes any point-in-time-integrity gap under Core Design Principle
   #10 (`MASTER_PLAN.md` §3), not only a testability one.
5. **`MomentumPolicy` import-time config read.** Its dataclass field defaults
   (`short_window: int = _get_default_short_window()`) are evaluated once, at class-definition
   time, requiring the TOML config to already be loaded merely to import the module. This is
   used by `src/orchestrator/analysis_tools.py`, not dead code. `MomentumConfig` (the model the
   CLI/workspace actually run through) already avoids this via `Field(default_factory=...)`;
   apply the same lazy pattern to `MomentumPolicy`.
6. **Momentum series API.** `run_analysis` already computes full rolling SMA series
   (`close_series.rolling(window=s_win).mean()`) and then discards everything except
   `.iloc[-1]`. Expose a pure, vectorized function returning the full computed series (SMA
   short/long, RSI, crossover) beneath the existing snapshot-returning public API, so a caller
   evaluating many points in one series does not pay one full fetch-and-recompute per point.
   Scoped to Momentum only — Graham Number, Graham Growth, and FCF/Earnings Growth evaluate once
   per fiscal period, not once per bar, and a per-bar series API would be speculative generality
   for those three, not a real need.
7. **Publish JSON Schemas for `--json` payloads, backed by real typed envelope models.** Each
   analysis's JSON output already carries a stable `schema_version`, but none of the four
   `--json` builders (`_number_payload`, `_growth_payload`, Momentum's `_payload`, FCF's
   `_json_value(result)` plus manual field additions) construct their output from a Pydantic
   model or any single dataclass — they build or reshape a plain `dict[str, Any]` by hand.
   Confirmed by inspection: FCF's builder calls `asdict()` on the native
   `FCFEarningsGrowthResult` dataclass and then bolts on `security_identity`/`instrument_kind`
   keys that aren't part of that dataclass at all; Graham's and Momentum's builders are hand-
   written dict literals with no backing model whatsoever. **Decided (with a caveat surfaced for
   review):** "generate the schema from the models" is only genuinely drift-proof, rather than a
   one-time snapshot that can silently go stale, if a real typed envelope model exists for each
   analysis's current output shape and the payload builder is changed to construct/validate
   through that model (e.g. via `.model_dump(mode="json")`) instead of a raw dict — at that
   point `.model_json_schema()` is generated from the same model that produces the real output,
   so drift becomes a `mypy --strict` or Pydantic validation failure, not a silent gap. This is
   more work than either hand-authoring a schema once or generating one from whatever dataclasses
   already happen to exist, but it is the only version of "generated, not hand-authored" that
   actually delivers what that preference is for. The lighter alternative — hand-author schemas
   now and add a test that validates real live/fixture output against them — remains available if
   the envelope-model approach turns out to be more than this slice should take on.
   **Decided:** publish the generated schemas as a checked-in `schemas/` directory (one versioned
   file per analysis/`schema_version`), not only behind a CLI flag — an external harness should be
   able to read or vendor a schema file directly without first being able to invoke `ian`, and a
   checked-in file gives a real PR diff whenever a schema actually changes. An optional
   `--json-schema` flag may still be added later as a cheap convenience once the files exist; it is
   not the primary artifact.

Excluded: any new trading-signal, entry/exit, or order-generation capability; a
`compute_series`-style API for the three fundamentals-based analyses; an actual MCP server,
subprocess boundary, or harness adapter (this work package makes that future possible, it does
not build it); backtester-specific integration code for any named external project; changing any
analysis's existing formulas, classifications, or presentation contracts beyond what's needed to
fix the specific defects above; the `src` → real package rename, moved out to its own work
package (`PKG`, see `IMPLEMENTATION_PLAN.md` row 12) given its scale relative to everything else
here.

## 3. Sequencing

Each slice ends with the managed quality gate and is gated by explicit authorization before the
next begins, matching this project's established slice convention.

| Slice | Scope |
| :--- | :--- |
| IR.1 | License declaration fix (`pyproject.toml` → Apache-2.0, per the project owner's authorization above). `MOMENTUM.md`'s correction already landed ahead of this slice. |
| IR.2 | Unify the analyzer return contract: type `BaseAnalyzer.run_analysis` generically, bring `FCFEarningsGrowthAnalyzer` under it. Revisit once Step 3.5's Piotroski analyzer exists as a real second data point. |
| IR.3 | Momentum calculation purity: injected clock, `as_of`-aware quality check independently re-verified (not delegated to the resolver), lazy `MomentumPolicy` defaults. |
| IR.4 | Momentum series API: pure vectorized series function beneath the existing snapshot API. |
| IR.5 | Typed JSON envelope models for all four analyses (or the lighter hand-authored-plus-test alternative, per the open question below) and the JSON Schemas generated from them. |

## 4. Acceptance criteria

- No existing analysis's formulas, classifications, exit codes, or presentation output changes
  for any currently-passing test or documented example, except where a slice's own scope is
  explicitly to add a genuinely new function (IR.4, IR.5) — additive, not substitutive. IR.1 (the
  license declaration) and IR.2 (the analyzer return-type contract) touch neither analysis output
  nor presentation at all.
- The complete managed gate (`scripts/run-quality-gates.ps1` / `.sh`), ≥85% coverage, after every
  slice.
- Each slice's own regression tests cover the specific defect it fixes.
- A final acceptance record analogous to this project's other work-package acceptance records.

## 5. Open questions for review

1. **Resolved:** IR.3's duplication becomes independent, trust-but-verify re-checking at both the
   resolution and calculation boundaries, not delegation to the resolver's earlier check.
2. **Resolved in direction, one caveat open:** IR.5 uses generated (not hand-authored) schemas,
   backed by real typed envelope models rather than the current hand-built dicts. The open part
   is scale: introducing four new envelope models (one per analysis) and changing each payload
   builder to construct through one is more work than a one-slice schema-publishing task might be
   expected to be. If that turns out to be too much for one slice once scoped in detail, IR.5 may
   need to split into "introduce envelope models" and "generate and publish schemas from them" as
   two slices, or fall back to the lighter hand-authored-schema-plus-drift-test alternative
   described in §2 item 7. Decide once IR.5 is actually scoped, not here.
3. **Resolved:** IR.5 publishes to a checked-in `schemas/` directory as its primary artifact; see
   §2 item 7.
4. **Open:** IR.3's independent re-check means `run_with_context` calls `publish_quality(decisions)`
   twice for the same underlying data — once inside `MomentumInputResolver.resolve()`, once inside
   `run_analysis`'s own newly-independent check — publishing the same quality decisions to
   telemetry twice per call. Proposed resolution (project owner, 2026-09-24): keep `run_analysis`'s
   own check running unconditionally (the defense-in-depth guarantee IR.3 decided on), but suppress
   its own `publish_quality` call specifically on the path reached from `run_with_context`, where
   the resolver has already published. `run_analysis` cannot key this off whether `df` was supplied
   — confirmed by inspection, `run_with_context` always passes a concrete
   `df=resolved.market_data.frame`, never `None`, so "was a frame given" cannot distinguish "the
   resolver already published for this frame" from "an external caller supplied its own frame
   directly" (the public preloaded-frame API, which has no resolver and must still publish). The
   IR review should settle the exact signal `run_with_context` uses to suppress the duplicate
   publish (for example, a private parameter it alone sets) without adding a public-facing knob
   other callers need to know about.
5. **Open:** Making `run_analysis`'s own quality check `as_of`-aware (IR.3) requires adding a new
   parameter to its public signature, which today has none (`config`, `ticker`, `df` only). An
   optional parameter defaulting to `None` preserves every existing caller's behavior exactly, so
   this is a small, backward-compatible addition — one sentence in the IR.3 slice's own contract,
   not a design fork.
