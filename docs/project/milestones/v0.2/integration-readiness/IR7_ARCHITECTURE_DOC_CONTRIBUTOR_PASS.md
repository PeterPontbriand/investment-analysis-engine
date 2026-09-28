# IR.7 — ARCHITECTURE.md Contributor Pass

Documentation-only slice bringing `docs/project/ARCHITECTURE.md` back into agreement with the
current codebase and reorganizing it for a first-time contributor. Numbered and approved for
implementation by the project owner. **Implemented and complete** on `fix/ir7-architecture-doc-pass`,
branched from `feat/ir-integration-readiness` (not `main` — see §8). See the completion record at
the end for what actually happened, commit by commit, and the final §5 outcome table — including
"Read-through corrections" and "Final-pass corrections", two rounds of stakeholder read-through
that together found acceptance criterion 2 was not fully met at first submission and fixed it in
eighteen further commits, three of which were regressions the first correction round introduced.

## 1. Problem

`ARCHITECTURE.md` accumulated drift the way any living architecture document does: sections were
inserted without renumbering child subsections, "target" labels were never removed once the target
shipped, a module-layout diagram was written once and never regenerated, and prose was edited
enough times that at least one sentence now contradicts itself mid-paragraph. None of this is a
correctness defect in the software — it is a documentation-trust defect: a contributor reading
`ARCHITECTURE.md` today cannot tell, from the document alone, which parts describe what actually
runs.

A second, now-merged branch (`docs/contributor-documentation`) independently reached a similar
conclusion and rewrote the file from a snapshot several slices behind this one (before IR.2.1
through IR.2.4). That rewrite was not taken — see merge commit `35141ea` for why — but it is real
source material for this slice, not a competing version of record. §6 says specifically what was
taken from it.

## 2. Evidence (verified against the pre-slice tree)

### 2.1 Stale "target"/"planned" labels on implemented features

- **§4 `AnalysisRun` — labeled "(Step 3.4 target)".** Step 3.4 (the local research workspace) is
  complete: `git log` shows `a12b790`/`89f62af` "feat(workspace): complete the local research
  workspace (Step 3.4) (#37)", and `src/data/repositories/analysis_runs.py` and the entire
  `src/workspace/` package (16 files) exist and are exercised by `tests/workspace/` and
  `tests/test_workspace_integration.py`.
- **§4 "Watchlist / refresh workspace" — labeled "(Step 3.4 target)".** Same evidence:
  `src/data/repositories/watchlists.py`, `src/workspace/watchlists.py`, `src/workspace/refresh.py`,
  and the `ian watchlist` / `ian runs` CLI surface are implemented and are the direct subject of the
  planned IR.6 slice, which fixes a *lifecycle gap* in an already-shipped feature.
- **§4 "Resolved-input cache seam" — "Durable SQLite-backed caching remains Step 3.1."** Step 3.1
  shipped (`b64669f`, #28), and `SQLiteResolvedInputCache` is listed two sections later in the same
  document (§6) as an existing repository with a public contract.
- **§10 "Database readiness..." — "The current migration bundle has only `0001_persistence`."**
  `alembic/versions/` currently has four bundles. Stale by three migrations.
- **§10 "Planned Graham comparison evidence repair."** Contradicted eight sections earlier by §8.1,
  which already describes the repair as implemented, and by production code
  (`src/data/security_unit.py`, `src/reporting/valuation_presentation.py`, covered by
  `src/evaluation/fixtures/sec_edgar_fpi.py`-backed tests).

### 2.2 `BaseDataClient` vs `MarketDataProvider`

Both real and distinct, undocumented as such: `BaseDataClient(ABC)` is the legacy concrete client;
`MarketDataProvider(Protocol)` is the real resolver-facing boundary Momentum uses, with
`BaseDataClient` adapted into it via a private `_ClientProviderAdapter`. `ARCHITECTURE.md` presented
both as if each were *the* historical-price boundary, with no cross-reference between them.

### 2.3 Two inconsistent `DATABASE.md` links

§6 line 365's `docs/user/DATABASE.md` was broken (resolves to a nonexistent path); §10 line 615's
`../user/DATABASE.md` was correct.

### 2.4 Misfiled sections

"Typed SQLite repositories and administrative inspection" had no owning `##` parent. "Planned
Graham comparison evidence repair" and "Database readiness and explicit maintenance" were filed
under `## 10. Failure and reliability boundary`, which neither is about.

### 2.5 Data-flow diagram omitted two of four strategies' paths

§7's diagram showed only the Graham path — no FCF resolver branch, no instrument-profile flow.

### 2.6 Inconsistent "current vs. planned" labeling convention

At least three phrasings for the same concept across headings, no stated rule, no removal once a
label goes stale (§2.1 is the direct consequence).

### 2.7 Wording defects

A stray "the" before "Massive," and a circular sentence restating "SEC financial facts" twice.

### 2.8 Invariant cross-references

Repo-wide `git grep` for numeric invariant citations (`invariant [0-9]+`, `invariant #[0-9]+`)
across every tracked `.md` and `.py` file returned **zero matches outside `ARCHITECTURE.md`'s own
numbered list**. No other document, docstring, or code comment cited an architectural invariant by
number, so condensing/renumbering §1 could not break an external reference.

Inside `ARCHITECTURE.md` itself, there was exactly one cross-reference into §1, and it was already
stale, independent of any renumbering: §4's "Durable instrument profiles" section said durable
persistence matched "the 'Traceable, Time-Bounded Inputs' and 'Decoupled Contracts' invariants
(§1)" — neither name matched any of the 18 invariants' actual titles (the closest was
"Time-bounded provenance," not "Traceable, Time-Bounded Inputs"; nothing titled "Decoupled
Contracts" existed at all).

## 3. Target outline (implemented)

1. Purpose, and how current versus planned content is marked
2. Architectural invariants
3. System overview
4. Composition roots and dependency wiring *(new)*
5. Time and the analysis boundary
6. Analysis strategies: the boundary
7. Data providers and input resolution
8. Persistence
9. Presentation and reports
10. Orchestration and evaluation
11. Reliability, logging and telemetry
12. Planned work
13. Module boundaries
14. Contributor guardrails

## 4. Outline item 6: "Analysis strategies: the boundary"

Originally scoped as "Strategies: Momentum, Graham Number, Graham Growth Value, FCF & Earnings
Growth" — itself a catalogue. Two signals argued against any strategy catalogue in
`ARCHITECTURE.md`:

- `docs/user/strategies/README.md` already lists current strategies for an investor audience; that
  is the correct, single place a reader goes to learn which strategies exist. The Contributor Guide
  does *not* enumerate strategies by name either — its "current analyzer contract" section
  describes the shared contract generically.
- `docs/contributor-documentation`'s rewrite added its own strategy-list paragraph to
  `ARCHITECTURE.md`. Not taken into this branch (merge commit `35141ea`), and not a precedent to
  repeat: a third catalogue would drift from `docs/user/strategies/README.md` the moment a strategy
  is added — exactly what invariant 3 ("Heterogeneous strategies") and the Contributor Guide's own
  existence already guard against.

Implemented scope for §6: what a strategy owns versus what it shares, the independence rule, and
two links — the Contributor Guide for how to add one, the user strategy guides for which ones
exist. No strategy names, no per-strategy policy defaults, no formula content anywhere in the
section. The originally-proposed "Adding a strategy" walkthrough inside `ARCHITECTURE.md` was
dropped entirely; the Contributor Guide already is that walkthrough.

## 5. Strategy-specific content: destinations and outcomes

Rule applied to every row sent to a user strategy guide or `FINANCE_MATH.md`: verify the
destination first; delete-only if already covered; add only the missing substance if not; record
the outcome. See the completion record for the final table — every row below was resolved, not
left implicit.

| Original content (§, subsection) | What it said | Category |
| --- | --- | --- |
| §4, `MomentumAnalyzer` | SMA/RSI window defaults, `MomentumPolicy` | Method semantics |
| §4, Graham analysis | Method identifiers, three-year-average EPS default, explicit AAA-yield input | Method semantics |
| §4, FCF & Earnings Growth analysis | 5→4→3 horizon fallback, classification basis, forward-EPS policy | Method semantics |
| §4, `FinancialFactsProvider` boundary | Per-strategy provider routing | Provider concern |
| §4, Security identity and instrument applicability | Provider precedence; presentation formatting | Mixed |
| §4, Method-specific Graham input resolution | Override → cache → provider → unavailable chain | Shared resolver pattern |
| §4, Method-specific Graham input resolution | Fiscal-year-end basis on derived BVPS (illustrative) | Method semantics (apparent) |
| §4, Resolved-input cache seam | In-memory/fixture-backed `get`/`put` | Shared infrastructure |
| §4, Durable instrument profiles | `SQLiteInstrumentProfileRepository`, ticker-reuse rule | Shared infrastructure |
| §4, Durable instrument profiles | ETF aggregate FCF (planned) | Planned |
| §4, Resolved input and provenance models | Typed provenance fields | Shared infrastructure |
| §4, Fixture-backed data capabilities | What Golden fixtures prove | Shared infrastructure |
| §4, Investor-facing result presentation | Concise/details/diagnostics/JSON grammar; schema bumps | Shared seam |
| §4, Investor-facing result presentation | "Maximum indicated price/screening ceiling"; AAA-yield warning wording | Method semantics |
| §4, `AnalysisRun` / watchlist workspace | Durable run record, refresh concurrency | Shared infrastructure |
| §4, `TrajectoryEvent`/Recorder/Sink | Telemetry sinks, sanitization | Shared infrastructure |
| §8.1, SEC FPI/IFRS seam | Accession selection, taxonomy regime, field mappings | Provider concern |
| §8.1, SEC FPI/IFRS seam | Security-unit gate | Provider concern (check) / method semantics (consequence) |

## 6. What was taken from `docs/contributor-documentation`'s rewrite

Source material, not a version of record — its merge base predates IR.2.1 through IR.2.4, so its
per-strategy and clock-model content was stale by several slices. Three organizational choices were
used:

- **The condensed, unnumbered invariants list style** — re-derived against the current 18-item
  list, not copied (their list was missing invariant 18 and others).
- **The "Module boundaries" bullet-list format** — seeded §13, extended with the six top-level
  `src/` packages their six bullets omitted (`core/`, `evaluation/`, `llm/`, `schema/`, `tools/`,
  `utils/`).
- **The unified persistence/artifacts data-flow list shape** — informed §8's diagram placement.

Not reused: the strategy-list paragraph, the simplified `AnalysisContext`/clock description
(superseded by IR.2.4's §5), and the condensed provider section (missing `MarketDataProvider` and
the security-unit gate entirely).

## 7. Decisions

- **D1 — Labeling: option (b).** No per-heading labels. §1 states everything outside §12 describes
  current behavior; §12 is the only place planned work appears.
- **D2 — Module layout: package-level map, no generated tree.** §13 is a hand-maintained,
  one-line-per-package list, verified against the real `src/` tree. No `git ls-files`-diffing gate
  check.
- **D3 — Repo-wide Markdown link/anchor checker: built and wired.** `scripts/check_doc_links.py`,
  offline, checks every tracked `.md` file, reports every break in one run, runs first in both
  quality-gate wrappers.

## 8. Branch and sequencing

**Branch: `feat/ir-integration-readiness`, not `main`.** `main`'s `ARCHITECTURE.md` predates
IR.2.1–2.4, the §3/§5 clock section, this session's renumbering, and the
`docs/contributor-documentation` merge — branching from it would have recreated the exact collision
`35141ea` resolved. `fix/ir7-architecture-doc-pass` branched from `feat/ir-integration-readiness`
and merges back into it directly.

## 9. Acceptance criteria

- Every internal link and anchor in `docs/project/ARCHITECTURE.md` resolves, verified by the D3
  checker (which also covers every other tracked Markdown file in the repo).
- Every statement about implementation status or a file path is backed by evidence recorded in the
  completion record below.
- §6 contains no strategy catalogue and no per-strategy policy/formula content; every row in §5's
  table has a recorded outcome.
- The Composition roots and dependency wiring section links to the Contributor Guide's execution
  trace rather than restating it.
- No heading in the document carries a current/planned label; §12 is the only section containing
  planned work.
- §13 is the package-level map, not a generated or hand-copied file tree.
- The full managed quality gate passes, including the D3 check.

---

# Completion record

Implemented on `fix/ir7-architecture-doc-pass`, branched from `feat/ir-integration-readiness`.
Merged back via merge commit `2b8a152` and pushed to `feat/ir-integration-readiness`
(`6c9e6a0..2b8a152`).

## Commits, in order

1. `2f177c2` — the repo-wide Markdown link/anchor checker (D3) and its tests, including a
   Unicode-punctuation fix found and fixed during the checker's own first real run (folded into
   this commit rather than left as a separate fix-a-bug-in-yesterday's-commit step).
2. `128f488` — every pre-existing broken link/anchor the checker found on its first repo-wide run:
   22 breaks, concentrated in three files, all relative-path errors rather than stale content.
3. `7a50888` — stale target labels removed (D1) and the self-contradicting "Planned Graham
   comparison evidence repair" section deleted outright (on rereading, its content was fully
   redundant with §8.1, not partially so as the draft plan assumed).
4. `4349722` — `BaseDataClient`/`MarketDataProvider` reconciled; the data-flow diagram gained the
   missing FCF and instrument-profile branches.
5. `b731b06` — invariants list condensed to unnumbered bullets (D1); fixed its own pre-existing
   stale self-reference.
6. `a940284` — method-semantic duplication removed wherever the user strategy guides and
   `FINANCE_MATH.md` already covered it (verified each one before deleting anything; nothing needed
   to be added to those docs).
7. `b9bdd02` — new "Composition roots and dependency wiring" section; the three per-strategy
   subsections replaced by one "Analysis strategies: the boundary" section with no catalog.
8. `5aa7f46` — module layout rewritten as a package-level map (D2); three step-sequencing
   guardrails removed as obsolete (the steps they gated are complete).
9. `14c13cb` — the pure reorder into the approved 14-section outline, plus the two external anchor
   references the renumbering broke.
10. `7faa5fa` — the checker wired into both quality-gate wrappers and the documented commands;
    `scripts/` added to the `mypy --strict` scope.

Immediately before this slice, on `feat/ir-integration-readiness` itself: `1458781` added
`graham-comparison` and `issue-17` to `milestones/README.md`'s directory list, found while
verifying that file's own list against the real tree.

## D1–D3, as applied

- **D1 — verified.** `grep -n "Step [0-9]" docs/project/ARCHITECTURE.md` after the reorder returns
  only body-prose mentions of a step number as a historical fact, never a heading label.
- **D2 — verified.** §13 is eleven one-line bullets, one per top-level `src/` package, checked
  against `find src -maxdepth 1 -type d`.
- **D3 — verified.** The checker generates anchors the way GitHub does, including Unicode
  general-punctuation stripping (found necessary by running it for real against headings with
  en/em dashes, not assumed from unit tests alone), reports every break in one run, and now runs
  first in both `scripts/run-quality-gates.{sh,ps1}` and the commands `docs/project/README.md`
  documents.

## §5 destination-table outcomes

| Content | Destination | Outcome |
| --- | --- | --- |
| Momentum SMA/RSI window defaults, `MomentumPolicy` | `MOMENTUM.md` + `FINANCE_MATH.md` | **Superseded.** Corrected on later review: this row's sentence ("`MomentumPolicy` owns the short/long/RSI defaults") was not kept in place as first recorded here — it was removed along with the rest of the `MomentumAnalyzer` subsection when commit `b9bdd02` replaced all three per-strategy subsections with the unified "Analysis strategies: the boundary" section. `MOMENTUM.md` already covers the actual defaults, so nothing was lost, but the original table entry mischaracterized this as a deliberate "kept, architectural" decision when it was actually deleted as part of a later commit. |
| Graham method identifiers, three-year-average EPS default, explicit AAA-yield input | `GRAHAM_NUMBER.md` / `GRAHAM_GROWTH.md` + `FINANCE_MATH.md` | **Already covered, deleted only.** Both guides' "Earnings basis" / "Required user-supplied values" cover this in more depth. Nothing added; default-value language removed from `ARCHITECTURE.md`. |
| FCF 5→4→3 horizon fallback, classification basis, forward-EPS policy | `FCF_EARNINGS_GROWTH.md` + `FINANCE_MATH.md` | **Already covered, deleted only.** Covered by "Quick start" and "Forward EPS policy". Nothing added; policy enumeration removed. |
| Per-strategy provider routing | §7 | **Kept, relocated.** Provider concern; moved to §7 unchanged. |
| Security-identity precedence + presentation formatting | §7 / §9 | **Kept, relocated as one block.** Moved to §7 with the identity subsection it lives in, rather than mechanically splitting the formatting sentence to §9. |
| Override → cache → provider → unavailable chain | §7 | **Kept, relocated.** Shared resolver pattern; moved to §7 unchanged. |
| "Fiscal-year-end basis on derived BVPS" (illustrative) | `GRAHAM_NUMBER.md` | **Kept, reason.** On rereading, this illustrates a general architectural rule (resolver annotations must be evidence-justified), not duplicated method semantics. Not moved. |
| Resolved-input cache seam | §8 | **Kept, relocated.** Moved unchanged. |
| Durable instrument profiles | §8 | **Kept, relocated.** Moved unchanged (its stale invariant-name citation fixed separately). |
| ETF aggregate FCF (planned) | §12 | **Moved.** Relocated into the new §12, reformatted to that section's bulleted style — the one deliberate wording change surfaced by the reorder's own word-level verification. |
| Resolved input and provenance models | §7 | **Kept, relocated.** Moved unchanged. |
| Fixture-backed data capabilities | §7 | **Kept, relocated.** Moved unchanged. |
| Concise/details/diagnostics/JSON grammar + schema bumps | §9 | **Kept, relocated.** Shared seam; moved unchanged. |
| "Maximum indicated price/screening ceiling"; AAA-yield warning wording | `GRAHAM_NUMBER.md` / `GRAHAM_GROWTH.md` | **Already covered, deleted only.** Both guides state this in their own presentation. Nothing added; specific wording removed and replaced with a pointer. |
| `AnalysisRun` / watchlist workspace | §8 | **Kept, relocated.** Moved unchanged. |
| `TrajectoryEvent`/Recorder/Sink | §11 | **Kept, relocated.** Moved unchanged. |
| SEC FPI/IFRS seam: accession selection, taxonomy regime, field mappings | §7 | **Kept, relocated.** Moved, its own "8.1" sub-numbering dropped to match every other §7 subsection; content unchanged. |
| SEC FPI/IFRS seam: security-unit gate (the check) | §7 | **Kept, relocated.** Moved unchanged. |
| SEC FPI/IFRS seam: security-unit gate (the consequence) | `GRAHAM_NUMBER.md` / `GRAHAM_GROWTH.md` | **Already covered, nothing to delete.** Both guides' "Current-price comparison" sections already document this in more depth; no `ARCHITECTURE.md` prose duplicated it. |

## Reorder verification

Stripped every heading line (numbers/names were expected to change) and every blank/separator line
from the pre-reorder snapshot and the reordered file, then compared the remaining ~404 lines as a
multiset. Exactly one line differed on each side — the ETF-planned-work paragraph, accounted for
above — confirming every other paragraph, list item, table row, and diagram line moved unchanged.
The one other necessary text change (splitting the two-diagram intro sentence across §7 and §8) is
called out in commit `14c13cb`'s own message.

## Outstanding / not done

- The security-identity formatting sentence was kept with its identity subsection rather than
  split to §9 — a judgment call, not an oversight.
- No further "planned" items were found beyond ETF aggregate FCF; `FinancialFactsProvider`'s
  "no approved live AAA-yield series" note stays a stated limitation in §7, not §12, since there is
  no named future work item to point at there.
- Full managed quality gate passed after every commit that touched Python source; doc-only commits
  were verified with the checker plus a final full-gate run after the last Python change, per
  `AGENTS.md` §7's boundary (3188 tests, 91% coverage).

## Read-through corrections

**Acceptance criterion 2 — "every statement about implementation status or a file path is backed
by evidence recorded in the completion record below" — was not met at first submission.** A
stakeholder read-through of the version recorded above, verifying each factual claim against the
code rather than against this record, found eight false-or-contradictory statements and eight
clarity/staleness issues the original pass missed. All sixteen are fixed in eleven further
content-only commits on `fix/ir7-architecture-doc-pass`, each independently verified against the
code cited in its own commit message:

1. `64943d5` — added the missing "## 1. Purpose and how to read this document" heading over the
   intro paragraph (§9's outline calls for it; the reorder in `14c13cb` had left it out), and
   converted the header block's four backtick paths to real relative links the D3 checker can
   verify, dropping the "Step 2.3 implementation specification" entry (a single completed slice
   pinned in a document header meant to survive many slices).
2. `7a71f01` — §3's diagram named only `BaseDataClient` in the historical-series box though §7
   documents `MarketDataProvider` as the boundary Momentum's resolver actually consumes; added it.
   Rewrote "Step 3.4 later persists Analysis Runs..." in the present tense — Step 3.4 is complete
   and §8 already documents the persisted-run behavior as implemented.
3. `c5a97fe` — §4 listed `src/workspace/refresh.py` as a composition root performing "one
   composition per job." Verified against the code: per-job composition and the `executed_at` read
   happen in `cli_workspace.py`'s `_execute_*` functions; `refresh.py`'s own clock only timestamps
   each job's persisted `AnalysisRun` capture. Corrected, and named `cli_composition.py` /
   `cli_support.py` as the factory-helper modules the two real composition roots draw on.
4. `074c826` — §6 listed the shared `MetricResult` outcome type as something "every strategy
   shares." Grepped every strategy package: Momentum and FCF & Earnings Growth use it; neither
   Graham strategy does. Corrected to name it as a convention two strategies share, not a
   universal contract. Narrowed "invoked identically" to the shared `run_analysis` signature and
   noted execution adapters differ per strategy, per the Contributor Guide. Reworded an unclear
   sentence about extending a strategy's own layer.
5. `b259959` — three fixes: (a) §7's diagram had drifted out of column alignment in the
   instrument-profile-cache branch after earlier edits touched neighboring boxes; rebuilt with a
   small script that asserts column consistency rather than by eye. (b) `FinancialFactsProvider`
   was described as serving only the two Graham methods; FCF & Earnings Growth's input resolver
   (`src/analysis/strategy/fcf_earnings_growth/input_resolver.py`) consumes it too. (c) "Method-
   specific Graham input resolution" named the override/cache/provider/unavailable chain as if
   Graham-specific; it is a general pattern implemented once in the shared `InputResolver`
   (`src/data/financial/resolver.py`). Retitled to "Input resolution: override, cache, provider,
   unavailable" with the general pattern first and the Graham-specific inheritance detail as a
   sentence beneath it.
6. `65be04b` — deleted §8's "This storage layer does not introduce watchlists, investor Analysis
   Runs, new cache invalidation rules, or a second audit log" — directly contradicted by the
   `AnalysisRun` and watchlist/refresh subsections a few paragraphs later in the same section,
   which describe exactly those things as implemented.
7. `f9ebc57` — §9's "in the previous section" pointed at §7's identity subsection, but the reorder
   in `14c13cb` had already moved §9 two sections past it; removed the stale phrase, kept the link.
   §9's schema-version change log ("increment from 1 to 2 / 2 to 3") and §7's "Graham presentation
   schema 4" were both stale against `src/reporting/` (Momentum=4, Graham Number/Growth=6, FCF=5 at
   time of check) and did not reconcile with each other; replaced both with the underlying rule
   (identity is presentation metadata, versioned in each strategy's own presentation
   `schema_version`, independent of `result_schema_version`) instead of point-in-time numbers.
   Replaced the two remaining plain-text section references, `(§2)` and `` (§ `AnalysisRun` below) ``,
   with links to the section titles.
8. `368f966` — removed "(Step 2.1)" / "(Step 3.1)" from §11's telemetry-sink diagram (both shipped
   several slices ago) and rewrote "Step 2.6 owns hard execution/time/error caps..." in the
   present tense.
9. `3e67e5a` — rewrote the remaining step/milestone jargon in body prose to the present tense:
   "F-1 returns", "Approved pre-Golden P1 preserves", "Introduced minimally in Step 2.3", "Step 2.4
   reuses", "Step 2.2 establishes", and "in v0.2". Kept the one step-labeled link that points at an
   actual record (the P1 instrument applicability mapping record), dropping "proposed" from its
   surrounding sentence now that the mappings are implemented rather than proposed.
10. `6caf8e2` — replaced §10's by-name list of the four orchestration-tool handlers with a pointer
    to §6, and deleted §13's opening paragraph, which restated §6's "no shared strategy-specific
    base beyond `BaseAnalyzer`" claim with Graham-specific detail layered on top. Preserved the one
    non-duplicative fact it carried — the location of `shared/financial_resolution.py` — by folding
    it into the `src/analysis/` bullet in §13's package map.
11. `ebf7be6` — linked "Light Mode" in §2's invariants list to its definition in
    `docs/user/GLOSSARY.md#light-mode`; the term was previously used undefined and unlinked.

The full managed quality gate, including the D3 link/anchor checker, passed after the last of
these commits (3188 tests, 91% coverage, `check_doc_links` reporting zero breaks).

## Final-pass corrections

A second read-through, closer but not yet clean, found seven more issues — three introduced by
the first round of corrections above, four missed by both passes. Fixed in seven further
content-only commits on `fix/ir7-architecture-doc-pass`, each independently verified against the
code cited in its own commit message:

1. `d481e2e` — §4's "Every composition root reads `executed_at` exactly once" (added by commit
   `c5a97fe` above) contradicted the per-job reads described in the sentence immediately before it.
   Reworded to "exactly once per analysis it runs", matching §5's own phrasing of the same rule.
2. `14c7ce8` — §7's diagram (realigned by commit `b259959` above) showed the FCF annual-series
   resolver box as "◄── override/cache", the same label as the two Graham resolver boxes. Checked
   `ProductionAnnualGrowthSeriesResolver.resolve()` and `resolve_annual_growth_series()` in
   `src/analysis/strategy/fcf_earnings_growth/input_resolver.py`: neither takes an `override`
   parameter, only `cache`/provider/unavailable. Changed the FCF box's label to "◄── cache";
   the precedence section already only names the two Graham resolvers, so no further change needed
   there.
3. `2b567d3` — §8's "Typed SQLite repositories" table listed four repositories and omitted
   `SQLiteAnalysisRunRepository` (`src/data/repositories/analysis_runs.py`) and
   `SQLiteWatchlistRepository` (`src/data/repositories/watchlists.py`), even though the prose just
   below the table discusses both `AnalysisRun` and the watchlist/refresh workspace at length.
   Added both rows, public access and semantics read directly from each file. Checked every other
   file in `src/data/repositories/` (`trajectory.py`, `migrations.py`, `readiness_lock.py`,
   `sqlite.py`, `readiness.py`, `instrument_profiles.py`, `market_data.py`,
   `resolved_input_cache.py`): no other repository row was missing.
4. `1886391` — §3's diagram (the historical-series box named MarketDataProvider by commit
   `7a71f01` above) had grown long enough that "BaseDataClient / MarketDataProvider" pushed
   "FinancialFactsProvider" out of the "financial facts" column it needs to sit under. Split the
   two provider names across two lines so the second box lands back in its column.
5. `640fe8e` — §7's fixture-capability list named what Momentum's and Graham's fixtures prove but
   never mentioned FCF & Earnings Growth's, even though
   `src/evaluation/fixtures/fcf_earnings_growth.py` provides a deterministic
   `FixtureAnnualFinancialFactsProvider` with annual OCF/CapEx/EPS series. Added the missing bullet.
6. `3e0830c` — §6's `MetricResult` sentence (added by commit `074c826` above, correcting the
   original false "shared by every strategy" claim) still named the two strategies that currently
   use it. Named strategies drift the moment a third adopts the convention or one of the two stops;
   reworded to "some strategies use" — the sentence's function is to say `MetricResult` is not
   universal, not to enumerate who uses it, and §6 avoids strategy catalogues everywhere else for
   the same reason.
7. `629ce63` — two sentences the earlier read-throughs both missed were still phrased as a diff
   against an earlier state rather than a description of current behavior: "No durable evidence
   cache or database migration is introduced" (§7's SEC seam) and "retain their existing signatures
   and import paths as repository delegates" (§8's trajectory-sink paragraph). Rewritten as plain
   present-tense statements.

Three of these seven (items 1, 2, and 4) were regressions introduced by the read-through
corrections themselves, not missed on the first pass — a reminder that a correction pass needs the
same code-verification discipline as the original content, especially for anything touching a
hand-aligned diagram or a sentence built by editing another sentence in place.

The full managed quality gate, including the D3 link/anchor checker, passed after the last of
these seven commits (3188 tests, 91% coverage, `check_doc_links` reporting zero breaks).
