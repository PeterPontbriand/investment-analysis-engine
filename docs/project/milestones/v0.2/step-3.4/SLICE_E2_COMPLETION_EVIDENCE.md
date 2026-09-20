# Slice E2 — Completion evidence

**Review disposition:** pending review by the project owner.
**Date:** 2026-09-19 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

E1 was accepted before this slice began. The contract authorizes E2 (Number replay)
for a Cline/glm-4.7-flash implementation attempt now that E1 is accepted, so this
slice establishes the Graham Number v1 projection against the pattern E1 set for
Momentum: a dedicated `_project_*_v1` helper in `analysis_runs.py`, dispatched from
`project_run`, rendering only stored evidence through the live presenter.

## What the slice implements

Contract line 167 scopes E2 to "Number v1 projection helper and dispatch," with
acceptance: "All modes incl comparison unavailable, invalid and ETF fixtures; no
recalculation." Two pieces of work deliver that.

### The v1 projection helper and dispatch (`analysis_runs.py`)

`project_run` now routes the `("graham", "graham_number")` pair to a new
`_project_graham_number_v1`, mirroring E1's `_project_momentum_v1`. It decodes the
stored evidence (`GrahamNumberAnalysis`) and reconstructs a fully-populated
`GrahamNumberPresentation` from stored values only — `evidence.ticker`,
`evidence.assembly`, `evidence.result`, `evidence.as_of`,
`evidence.margin_of_safety_percent`, and `run.instrument_profile`. It then delegates
to the live `render_graham_number`.

The Graham Number value itself is stored in `evidence.result.value`, computed at
execution time and persisted; replay renders it, never recomputes it. Identity/kind
evidence comes from the envelope's own `instrument_profile` field rather than the
native analysis's copy — for the same reason E1 used it: the analyzer may leave
`GrahamNumberAnalysis.instrument_profile` unset, so replay must use the profile
captured on the run itself to render identity correctly. No analyzers, calculators,
providers, settings defaults, or clock are touched; `analysis_runs.py` has no such
import at all.

### Relocating the quote-reason normalization helpers (`graham.py` / `cli.py`)

The three private CLI helpers that classify optional quote failures into stable
investor-facing reasons — `_public_quote_reason`, `_number_with_public_quote_reason`,
and `_growth_with_public_quote_reason` — were moved from `src/cli.py` into
`src/reporting/graham.py` as public functions (`public_quote_reason`,
`number_with_public_quote_reason`, `growth_with_public_quote_reason`). This keeps
presentation-normalization logic in the reporting layer where it belongs and makes
it reusable by the replay path; `cli.py` now imports them. Behavior is unchanged —
the full suite passes with no CLI regression.

## Edge-case fixtures added (`test_analysis_run_replay.py`)

The `_graham_run` helper was extended to accept an optional stored `analysis`, so a
replay run can carry a specific failure state or a known-ETF profile instead of the
default OK result (ticker is derived from the analysis). Two new fixture builders
produce a NOT_APPLICABLE ETF analysis and an INVALID_INPUT analysis. Four tests were
added:

- **Invalid input** — `test_graham_project_run_invalid_input_renders_stored_failure_without_recalculation`.
  The fixture stores both EPS (4.0) and book value per share (10.0), which are
  sufficient to compute a Graham Number, yet replay renders the stored
  `INVALID_INPUT` status and its reason verbatim and shows no Graham Number — proof
  of consumption, not recomputation.
- **ETF / NOT_APPLICABLE** — `test_graham_project_run_etf_not_applicable_renders_stored_failure`.
  With a known-ETF profile, replay renders the stored `NOT_APPLICABLE` status and its
  company-level/ETF reason verbatim; no Graham Number is shown.
- **Comparison unavailable** — `test_graham_project_run_comparison_unavailable_renders_stored_result_without_price`.
  An OK result with no stored quote renders the Graham Number (42.00) but shows
  "Current price: unavailable" / "Price comparison: unavailable (no current quote)"
  rather than inventing a price.
- **All modes for the failure fixtures** — `test_graham_project_run_failure_fixtures_render_in_all_modes`.
  Both the invalid-input and ETF runs render in every `PresentationMode` without
  raising or fabricating a Graham Number, directly satisfying the "all modes incl …
  invalid and ETF fixtures" acceptance clause.

## Contract proof (line 167)

| Contract requirement | Evidence |
| :--- | :--- |
| Number v1 projection helper and dispatch | `_project_graham_number_v1` plus the `("graham", "graham_number")` branch in `project_run`, mirroring E1's Momentum path. |
| All modes | Pre-existing `test_graham_project_run_all_modes_render_from_the_reopened_run` (OK case) plus new `test_graham_project_run_failure_fixtures_render_in_all_modes` iterating every mode for the invalid-input and ETF fixtures. |
| Comparison-unavailable fixture | `test_graham_project_run_comparison_unavailable_renders_stored_result_without_price`. |
| Invalid-input fixture | `test_graham_project_run_invalid_input_renders_stored_failure_without_recalculation`. |
| ETF fixture | `test_graham_project_run_etf_not_applicable_renders_stored_failure` (known-ETF profile). |
| No recalculation | The invalid-input test stores EPS and book value per share that would compute a Graham Number and asserts none renders; the comparison-unavailable test asserts no price is fabricated. `analysis_runs.py` imports no calculator/provider/settings/clock. |

## Full managed gate

Ruff, Ruff format and strict mypy passed clean via
`scripts/run-quality-gates.ps1`. The full pytest run: **2,967 passed** (4 new in the
replay tests), combined coverage **91%**; `reporting/analysis_runs.py` reaches 100%
line/branch coverage and `reporting/graham.py` is at 92%.

## Correction (review round 1): replay now normalizes stored quote reasons

A review found one real fidelity gap in the first submission; everything else was
verified correct and is unchanged.

**The gap.** `_project_graham_number_v1` passed `evidence.assembly` straight into
`GrahamNumberPresentation`, so a run whose resolver quote lookup failed (for example
`assembly.quote_status == CalculationStatus.PROVIDER_ERROR`) replayed the raw technical
`quote_reason` (e.g. `"Provider error: connection reset"`) instead of the investor-facing
sentence the live command originally showed for that same execution. This is user-visible,
not cosmetic: `graham.py` surfaces `assembly.quote_reason` in the diagnostics line
(`graham.py:603`), the warnings path (`822`, `843`), and the rendered payload (`1026`,
`1085`). It also defeated the point of relocating the normalization helpers into
`graham.py` — replay now actually uses them.

**Why the original tests missed it.** None of the four new fixtures set
`quote_status`/`quote_reason`. The invalid-input test in particular *looked* like it
covered this, but it hardcoded the already-public sentence into the assembly's generic
`reason` field and left `quote_status` as `None`; because
`number_with_public_quote_reason` is a no-op when `quote_status` is `None`, that test
passed identically whether or not normalization ever ran.

**The fix.** `_project_graham_number_v1` now applies
`number_with_public_quote_reason(evidence.assembly)` before constructing the presentation
(`analysis_runs.py:144`), mirroring exactly what `cli._run_graham_number` does with
`number_with_public_quote_reason(assembly)` (`cli.py:782`).

**The new test's proof.**
`test_graham_project_run_normalizes_raw_quote_reason_to_public_sentence` stores a
deliberately raw technical reason on an OK assembly (successful Graham Number calculation)
with `quote_status == PROVIDER_ERROR`, then renders in DIAGNOSTICS mode — the one path
where `graham.py:603` interpolates `assembly.quote_reason` verbatim. It asserts the public
sentence is present and the raw string is absent. Because the stored reason is
verifiably different from the expected rendered text, the test can only pass if
normalization ran; it fails without the fix.

**Re-run gate.** Ruff, Ruff format and strict mypy passed clean via
`scripts/run-quality-gates.ps1`; the full pytest run is now **2,968 passed** (5 new in
the replay tests), combined coverage still **91%**. This supersedes the 2,967/4-new
figure above for this slice.

## Boundaries and review gate

No Growth replay was implemented — that is E3. No FCF replay (E4) or CLI wiring
(`runs show`, F2). Nothing was committed, pushed, or opened as a PR; this slice
awaits project-owner review of the evidence above.