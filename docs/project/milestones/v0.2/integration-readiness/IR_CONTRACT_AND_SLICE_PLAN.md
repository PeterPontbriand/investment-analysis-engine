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
| IR.4 | Momentum series API: pure vectorized series function beneath the existing snapshot API. **Label collision, not yet resolved in this file's own numbering: §6 below documents an unrelated "IR.4" (Python-version reproducibility), added directly to this branch on 2026-09-26 per explicit project-owner direction. See §6's own note for why the same label is reused despite this row.** |
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

## 6. IR.4 — Python-version reproducibility (ported to `fix/ir4-python-version-reproducibility`, 2026-09-26)

**This file, as inherited by this branch from `main`, is a stale snapshot.** Everything above this
section (§1–§5) predates all of IR's actual implementation work — `feat/ir-integration-readiness`
has since landed IR.1, unified the analyzer envelope (a much larger scope than this file's §2 item
3 describes), separated the Graham strategies, and unified clock sourcing, and its own copy of this
document is now 1,400+ lines. **Do not treat §1–§5 above as current** for anything beyond this
section; they are left untouched here deliberately (out of scope for this branch, per the
instruction that only IR.4-relevant sections land here) and will be superseded wholesale when
`feat/ir-integration-readiness` eventually merges to `main`.

**Why this section exists here at all, given that:** the authoritative version of this content
lives on `feat/ir-integration-readiness`, in that branch's own §7 (same numbering collision note
applies — that branch's document has five sections before it too, but many more in between; its
§7 is this section's origin, not a coincidence of numbering). **Per explicit project-owner
direction (2026-09-26), this branch's PR should carry both the IR.4 code changes and the IR.4 spec
in one diff, for single-diff review** — so the relevant sections are ported here rather than left
as a cross-branch reference only. This supersedes the original plan's own §7.7 (reproduced as §6.7
below), which said the fix branch must not edit this file; the project owner has since decided
the single-diff-review benefit is worth the documentation-merge-conflict risk this creates when
`feat/ir-integration-readiness` eventually merges `main` back in (§6.7 is updated accordingly, not
left contradicting the decision that produced this section's own existence).

**Label collision:** this file's own §3 table (line 137, above) already has a row named "IR.4"
for a different, unrelated slice — Momentum series API. That is this document's own inherited,
not-yet-resolved numbering; it is a different fork of the same original plan than the one where
"IR.4" was freed by a later renumbering and reused for the defect this section describes (see
`feat/ir-integration-readiness`'s own §2 item 7 / §3 for that history). This section keeps the
label "IR.4" anyway, because that is what the branch (`fix/ir4-python-version-reproducibility`),
this conversation, and the project owner have all been calling it — not because it resolves cleanly
against this file's own §3 table. Treat the two "IR.4"s in this file as referring to different
things from different forks of the plan, disambiguated only by section (§3's row vs. this §6).

The remainder of this section (§6.1–§6.7) is ported from `feat/ir-integration-readiness`'s §7.1–7.7
verbatim except for renumbered cross-references (`§7.x` → `§6.x`) and §6.7 itself, updated to
record the single-diff-review decision described above.

### 6.1 Reproduction (verbatim from the finding)

> On a clean checkout of `ad244bd` running Python 3.13.13, `uv sync --frozen` installed
> `pandas==3.0.5` (the version pinned in `uv.lock`), and `pytest` failed with 51 collection errors
> covering most of `tests/`. The cause is `src/data/repositories/market_data.py:138`:
> `def _index_storage(index: pd.Index[Any]) -> ...`. The module has no
> `from __future__ import annotations`. On Python ≤3.13, that annotation is evaluated when the
> function is defined. Runtime `pandas.Index` isn't subscriptable (only `pandas-stubs` makes it
> generic for mypy), so the import raises `TypeError: type 'Index' is not subscriptable`.
> `pandas==2.3.3` fails the same way, so this is not a pandas-3 regression. The line dates from
> `b64669f` (2026-09-06), so IR.2.3 didn't cause it. With a runtime monkeypatch to get past
> collection, the suite matched the reported gate: 3,129 tests and 91% coverage. The only failures
> were 16 subprocess-based tests that didn't inherit the patch.

### 6.2 Confirmed: which Python/pandas this project's own gate actually runs on

Checked directly in the environment every IR.2.x gate on `feat/ir-integration-readiness` has been
run from:

```
python3 --version        → Python 3.14.7
uv run python --version  → Python 3.14.7
uv run python -c "import pandas; print(pandas.__version__)"  → 3.0.5
```

Python 3.14 defers annotation evaluation by default (PEP 649), so
`_index_storage`/`_restore_index`'s `pd.Index[Any]` parameter/return annotations import cleanly
here without ever being evaluated — masking the defect in every gate that document has reported so
far. The reproduction's Python 3.13.13 diagnosis is confirmed, not merely plausible.

This is compounded, not caused, by CI: `.github/workflows/ci.yaml`'s matrix is
`python-version: ["3.14"]  # Aligned with your local environment target` — three operating systems,
one Python version. `pyproject.toml` declares `requires-python = ">=3.12"` and no `.python-version`
file exists, so a fresh `uv sync` on any machine whose ambient/selected interpreter is 3.12 or 3.13
reproduces the reported failure, and CI has never exercised either version to catch it. Both gaps
are addressed below (§6.5).

### 6.3 Annotation audit (baseline: `main`, not `ad244bd`; authoritative audit is implementation's job)

**Audit baseline correction: IR.4 branches from `main`, so the audit that matters is against
`main`'s tree, not `ad244bd` (a `feat/ir-integration-readiness` commit).** The two trees differ for
exactly this defect class: `main` does **not** have IR.1 item 2a's `momentum_analyzer.py` fix —
verified directly (`git show main:src/analysis/strategy/momentum/momentum_analyzer.py` still shows
`_calculate_rsi(close: pd.Series[float], ...)` at line 277 with no `from __future__ import
annotations`). That fix exists only on `feat/ir-integration-readiness`. `market_data.py` is
byte-for-byte identical between the two branches (`git diff main feat/ir-integration-readiness --
src/data/repositories/market_data.py` is empty), so its part of the finding is unaffected.

**The grep below is a quick first pass, not the audit.** It only catches one shape of one defect
class — a stub-only pandas generic subscript, textually matched. Python 3.14's default lazy
annotation evaluation (PEP 649) hides a strictly wider set of import-time failures on 3.12/3.13,
including at least: unquoted `TYPE_CHECKING`-only names used in a runtime-evaluated annotation
(e.g. an import guarded by `if TYPE_CHECKING:` but referenced unquoted in a signature outside one);
a forward reference to a name defined later in the same module; other stub-only generics beyond
`pandas` (any third-party type that is only generic through its `-stubs` package); and any
3.13+/3.14-only syntax or stdlib API used anywhere reachable at import time, not only in an
annotation. The grep also only searched `src/`, not `tests/`, which import `src` modules and could
independently hit any of the same failure modes in their own annotations or module-scope code.

Quick pass, run directly against `main`'s tree:

```
git show main:src/analysis/strategy/momentum/momentum_analyzer.py | grep -n 'pd\.\(Index\|Series\|DataFrame\)\['
git show main:src/data/repositories/market_data.py | grep -n 'pd\.\(Index\|Series\|DataFrame\)\['
# repeated across every src/ and tests/ file at implementation time, not just these two
```

On `main`, this quick pass surfaces two files, **both unsafe**:

- `src/analysis/strategy/momentum/momentum_analyzer.py:277` — `_calculate_rsi(close:
  pd.Series[float], ...)`. **Unsafe on `main`** (unlike on `feat/ir-integration-readiness`, where
  IR.1 item 2a already added `from __future__ import annotations`). **In scope for IR.4**: apply
  the identical one-line fix to `main`'s copy. Because it is textually identical to the fix already
  present on `feat/ir-integration-readiness`, merging `main` back into the feature branch after
  IR.4 lands (§6.7) resolves this file as a clean no-op, not a conflict — the feature branch
  already has the same line.
- `src/data/repositories/market_data.py` — unsafe, two occurrences, both function signatures, no
  `from __future__ import annotations`: line 138 (`def _index_storage(index: pd.Index[Any]) -> ...`)
  and line 200 (`def _restore_index(...) -> pd.Index[Any]:`). A third occurrence, line 202 (`index:
  pd.Index[Any]`, inside `_restore_index`'s body), is a bare local-variable annotation with no
  assignment on that line; CPython does not evaluate a local variable's annotation expression at
  runtime (verified directly: a bare `x: Bar[int]` inside a function body does not raise even when
  `Bar.__class_getitem__` raises unconditionally), so it is not part of the defect.

IR.1 item 2a's own audit for this defect class was scoped only to `src/analysis/strategy/*/*.py`,
which is why `market_data.py` was missed the first time — a further reason not to trust a
textually-scoped grep as the final word here.

**Authoritative audit (required before this slice is accepted): on a Python 3.12 interpreter,
against `main`'s tree (the branch IR.4 actually starts from):**

```
uv run --frozen --python 3.12 python -m compileall -q src tests
uv run --frozen --python 3.12 python -c "import pkgutil, importlib, src; [importlib.import_module(m.name) for m in pkgutil.walk_packages(src.__path__, 'src.')]"
uv run --frozen --python 3.12 pytest --collect-only -q
```

`compileall` catches any remaining syntax-level 3.13+/3.14-only construct across both `src/` and
`tests/`; walking and importing every `src` submodule forces every module-scope annotation and
top-level statement to actually execute, which a partial import graph (only whatever the test suite
happens to reach) would not guarantee; a full `pytest --collect-only` forces collection of every
test module, catching a `tests/`-side occurrence the grep never looked for. All three must pass
clean (no `TypeError`, `NameError`, or `SyntaxError`) before §6.6's acceptance criteria are
considered met. Treat this command sequence, not the grep, as the source of truth for "every
occurrence is fixed"; apply §6.4's per-file remedy judgment to anything it finds beyond the two
files already identified.

### 6.4 Chosen remedy

**Two files, one remedy: add `from __future__ import annotations` (a targeted, per-file future
import) to both `main`'s `momentum_analyzer.py` and `market_data.py`.** Not quoted annotations on
just the affected signatures, and not a `TYPE_CHECKING`-only alias — a plain file-wide future
import is this project's existing, precedented remedy for this exact defect class (IR.1 item 2a),
and using it for both files keeps one remedy style across the codebase.

- **`momentum_analyzer.py`**: re-apply the exact one-line fix IR.1 item 2a already landed on
  `feat/ir-integration-readiness` (§6.3) to `main`'s copy. No new runtime-annotation analysis is
  needed beyond what item 2a already did — `main`'s version of this file has the same
  `MomentumConfig(BaseModel)` plus plain `@dataclass(frozen=True)` classes as the feature branch's
  copy (checked directly: `git show main:.../momentum_analyzer.py` shows the identical class shapes,
  no `TypeAdapter`, no SQLAlchemy), so item 2a's already-gate-verified safety conclusion applies
  unchanged. The one-line diff is textually identical to the feature branch's own fix.
- **`market_data.py`** (unchanged from the original analysis — this file is identical between
  `main` and `feat/ir-integration-readiness`, §6.3): explicit check against runtime-read
  annotations, required by this slice, not assumed:
  - `market_data.py` defines `@dataclass(frozen=True)` classes `MarketDataCacheKey` and
    `MarketDataCacheEntry`, one of which (`MarketDataCacheKey`) is wrapped in
    `_KEY_ADAPTER = TypeAdapter(MarketDataCacheKey)`, plus a Pydantic `_FrameMetadata(BaseModel)`.
    All three read annotations at runtime — `TypeAdapter` explicitly, to build its validation
    schema. Checked field-by-field: every field on all three (`ticker: str`, `request_start: date`,
    `cached_at: datetime`, `schema_version: int`, `key: MarketDataCacheKey`, `data:
    HistoricalMarketData`, `resolved_at`/`format_version`-style fields on `_FrameMetadata`, etc.) is
    a plain, always-real-at-runtime type — none depends on eager evaluation, and none is a pandas
    stub-only generic. A file-wide future import changes nothing about how any of these three
    classes resolve their own annotations; `TypeAdapter`/Pydantic already resolve
    `from __future__ import annotations`-deferred annotations correctly (standard PEP 563 support),
    and `momentum_analyzer.py`'s own `MomentumConfig(BaseModel)` already proves a Pydantic
    `BaseModel` coexists safely with this project's future-import convention.
  - No Typer command signature lives in this module (Typer commands are in `src/cli.py`,
    unaffected).
  - SQLAlchemy usage here is Core-style (`Table`/`Column` objects imported from
    `src.data.repositories.schema`), not declarative ORM classes with `Mapped[...]` annotations, so
    the declarative-annotation-resolution risk item 2 warns about does not apply to this file.
  - **Implementation must still add a regression test** that imports
    `src.data.repositories.market_data` and exercises `_KEY_ADAPTER`/`_FrameMetadata` under
    whichever Python version CI now tests (§6.5), not merely assume this analysis — matching this
    project's "verify, don't assume" convention.

**If §6.3's re-run at implementation time finds a new occurrence in a file with genuinely
real-type-dependent runtime introspection where a file-wide future import is not obviously safe**,
fall back to quoting just that occurrence's annotation (`index: "pd.Index[Any]"`) instead, and
record the reason inline as a comment at that one call site — do not apply a blanket rule if a
specific file's mix of constructs makes the file-wide import genuinely uncertain.

### 6.5 Python policy

**Decision: keep `requires-python = ">=3.12"` (matches `AGENTS.md` §5's "Target Python 3.12+" and
IR.1 item 2a's already-recorded rejection of narrowing to `>=3.14`); fix the code so the declared
range is genuinely true; enforce it so this cannot silently regress again.**

1. **`pyproject.toml`**: no change — `requires-python = ">=3.12"` already states the intended
   policy correctly. The defect was that the policy was never honored or tested, not that it was
   wrong.
2. **`.python-version`: add one, pinning `3.12`** (the lowest declared-supported version, not the
   newest). A `uv sync` run without an explicit interpreter picks this file's version by default;
   pinning to the *oldest* supported version means routine local development exercises the
   strictest, most eager-evaluation-prone interpreter by default, so a regression of this exact
   kind fails immediately for a developer instead of silently passing until someone happens to run
   an older interpreter or a clean-checkout audit finds it again. (Pinning to 3.14 instead would
   keep masking this defect class the same way the current absence of a pin already does.)
3. **`.github/workflows/ci.yaml`: widen the matrix to `python-version: ["3.12", "3.13", "3.14"]`**,
   removing the `# Aligned with your local environment target` comment (no longer accurate once the
   matrix covers the declared range, not one developer's machine). This is the actual enforcement
   mechanism — a `.python-version` pin only changes the *default* for an unqualified `uv sync`; only
   a multi-version CI matrix proves every declared version keeps working.
4. **`uv.lock` consistency**: confirm `uv lock` resolves one consistent, correct dependency set
   across the full `>=3.12` range (not narrowly resolved against 3.14 only) — re-run `uv lock`
   after the annotation fix and diff it; if `uv` reports environment-marker-conditioned resolution
   differences between 3.12/3.13/3.14 for any package, record what they are and confirm each
   resolved version is independently compatible with this project's runtime code, not only with
   3.14's.
5. **`[tool.mypy] python_version = "3.14"` (`pyproject.toml`) is wrong and must change to `"3.12"`
   — corrected after review; the first draft of this item called it orthogonal, which is itself a
   defect of the same class.** Targeting `3.14` means mypy assumes every 3.13+/3.14-only stdlib API
   and typing feature is available and never flags one used on a code path that must also run on
   3.12 — the exact same "looks fine under the newest interpreter, breaks on the oldest declared
   one" failure mode as the eager-annotation defect this slice exists to fix, just surfaced through
   type-checking instead of import-time evaluation. Set `python_version = "3.12"` so mypy checks
   against the floor of the declared range, not its ceiling. **This may surface real type errors
   that `python_version = "3.14"` was silently hiding; fix them within IR.4 — do not suppress a
   newly-surfaced error with `# type: ignore` or a per-module mypy override**, since either would
   just recreate this same "passes under one interpreter's assumptions, wrong under the declared
   floor's" defect one layer up, inside the type-checking config itself.
6. **Checked `[tool.ruff] target-version` (`pyproject.toml`): already `"py312"`.** No change
   needed — recorded here because an above-floor `target-version` would let the formatter and
   `UP` (pyupgrade) lint rules emit or accept newer-only syntax (e.g. a construct only valid on
   3.13+), the same risk class as item 5, and this project's own convention (per this slice) is now
   to check every Python-version-sensitive tool setting rather than assume one config axis implies
   another.

### 6.6 Acceptance criteria

From a fresh clone, run each version **explicitly**, not by relying on whatever `.python-version`
happens to default to — §6.5 pins that default to `3.12`, so a bare `uv sync`/`uv run` on all three
"checks" would silently run 3.12 three times and prove nothing about 3.13/3.14. Pass both `--frozen`
and `--python` on every command: `uv run` syncs before running and can rewrite `uv.lock` on its own,
so `--frozen` belongs on the `uv run` invocation itself, not on a separate `uv sync` step that a
plain `uv run` would silently redo anyway — a `uv sync --frozen` followed by an unqualified
`uv run` never actually exercises the frozen sync.

```
# 3.12 (also the .python-version default; still pass --python explicitly to prove it, not assume it)
uv run --frozen --python 3.12 python --version   # must print 3.12.x before proceeding
uv run --frozen --python 3.12 pytest

# 3.13
uv run --frozen --python 3.13 python --version   # must print 3.13.x before proceeding
uv run --frozen --python 3.13 pytest

# 3.14
uv run --frozen --python 3.14 python --version   # must print 3.14.x before proceeding
uv run --frozen --python 3.14 pytest
```

Each `python --version` check is not decorative — it is what catches the silent-repeat failure
mode above if `--python` is ever dropped or mistyped in a future run of this checklist.

- All three command groups above pass with no manual steps, no monkeypatch, and no
  environment-specific workaround, and each one's `python --version` line confirms the interpreter
  it actually ran on.
- The managed quality gate (`scripts/run-quality-gates.ps1` / `.sh`) output states the Python and
  pandas version it ran on, so a future gate report is self-verifying instead of requiring someone
  to separately ask "which interpreter produced this."
- `.github/workflows/ci.yaml`'s matrix actually exercises all three declared versions (as distinct
  matrix entries, each resolving to the version it claims) and is green on all of them.
- §6.3's authoritative audit (`compileall` + full-package import + `pytest --collect-only`, on
  Python 3.12) is run at implementation time and passes clean; the quick grep is not treated as
  sufficient on its own.
- Full managed gate passes (this slice touches Python source and CI configuration; it does not
  qualify for IR.1's docs-only exemption).

### 6.7 Plan location and branch mechanics (updated 2026-09-26 — supersedes the original version of this note)

**Original decision (still the plan of record on `feat/ir-integration-readiness`'s own §7.7):** the
fix branch reads its plan from `feat/ir-integration-readiness` without copying it, and must not
edit `IR_CONTRACT_AND_SLICE_PLAN.md` or `IMPLEMENTATION_PLAN.md` on the fix branch, to avoid a
second, divergent edit history for documents that already have one on the feature branch.

**Superseded by explicit project-owner direction, 2026-09-26: bring the IR.4-relevant sections of
both documents into `fix/ir4-python-version-reproducibility` itself** (this section, and the
corresponding `IMPLEMENTATION_PLAN.md` note), so a single PR diff on this branch carries both the
code and the spec it implements, for single-diff review. The project owner explicitly accepted the
tradeoff this creates: a documentation merge conflict (or a silent divergence, if the conflict is
resolved carelessly) when `feat/ir-integration-readiness` eventually merges `main` back in, since
both branches will have independently edited the same files. This is a deliberate, recorded
exception to the original plan, not an oversight.

- **What actually happens at merge-back time, given this section now exists here:** when `main`
  (carrying this section) merges into `feat/ir-integration-readiness` (carrying the much larger,
  independently-evolved §7 this section was ported from), `IR_CONTRACT_AND_SLICE_PLAN.md` will
  conflict — both branches touch the file, even though the touched *content* (§6 here vs. §7
  there) describes the same slice and is largely the same text. Resolve that conflict by keeping
  the feature branch's own §7 as authoritative (it is the actively-maintained copy, per §7.7's
  original reasoning, which this section does not change) and discarding this branch's §6 rather
  than trying to merge the two textually — §7 should also gain whatever acceptance/completion note
  IR.4's actual review produces, since completion is still recorded on the feature branch (below),
  not here.
- **Record IR.4's completion/acceptance on `feat/ir-integration-readiness`, after merging `main`
  back in — not on this fix branch, and not before the merge-back.** This part of the original
  decision is unchanged: once this fix branch is accepted and merged to `main`,
  `feat/ir-integration-readiness` merges `main` back, and *that* merge (or the commit immediately
  after it) is where `feat/ir-integration-readiness`'s own §7 gets its acceptance note — not this
  section, which will already be gone (discarded per the conflict resolution above) by the time
  that happens.
