# Spec portfolio-application-boundary: record the future portfolio application and settle portfolio scope

- **Owning plan:** [Master Plan §2.5 Product boundaries](../MASTER_PLAN.md#25-product-boundaries).
- **Branch:** `docs/portfolio-application-boundary`, from `main` at `4e82469`.
- **Decisions approved:** 2026-11-24.
- **Lane:** normal.

## Goal

Once this merges, the project's documents agree on where portfolios belong. A future portfolio application keeps an
investor's holdings. The engine computes portfolio-level evidence only from holdings supplied with a request. A desktop
issue records an overview screen for recent refresh outcomes and watchlists that need attention.

## Decisions

The decisions are recorded by this unit in the new "Decision record: portfolio application (2026-11-24)" section of
[Master Plan §2.5](../MASTER_PLAN.md#25-product-boundaries) (step 2). They are:

- B1: only this repository's documents change; the desktop repository gets one issue (B12) and no document change.
- B2: the decisions are recorded in Master Plan §2.5, as the 2026-11-01 product-boundaries record was; no new plan
  document.
- B3: the unit is named `portfolio-application-boundary`; no issue for the unit, no sequence-table row.
- B4: Master Plan §2.5 gains a row for a future portfolio application. It carries no name, working or otherwise.
- B5: Master Plan §2.5 gains a "Future portfolio application" subsection with two rules and two open questions (its
  user interface; holdings in saved runs).
- B6: Master Plan §2.5's opening states no count of applications.
- B7: the engine's "must not do" gains keeping an investor's holdings or transactions; so does the Discovery
  Workbook's §21 Non-Goals.
- B8: the Evidence Provider Roadmap's "Portfolio and account" rows stay in place, annotated in their "Existing plan"
  column, and two "Who would consume this" rows are adjusted.
- B9: the API contract plan's §4 Out of scope line about sectors links to the new subsection; A.13's I9 row is left as
  written.
- B10: the Discovery Workbook's §20 "Screening and portfolio construction" names the discovery loop and the portfolio
  application.
- B11: no name for the portfolio application appears in any document.
- B12: one desktop-repository issue for an overview screen.

## Out of scope

- Any code, test, served document or glossary change.
- Naming the portfolio application, or giving it a repository.
- Deciding whether the portfolio application gets its own GUI or is served by the Investment Analysis Desktop.
- Any note about sharing look-and-feel or plumbing between applications.
- A Master Plan §2.5 row for the discovery (market-scan) loop.
- Moving Evidence Provider Roadmap rows between families, or changing its counts of candidates or families.
- Rewording A.13 or its I9 row in the API contract plan.
- Any desktop-repository file.

## Allowed files

- `docs/project/specs/portfolio-application-boundary.md` (this spec; created by step 1's commit)
- `docs/project/MASTER_PLAN.md`: §2.5 only
- `docs/project/EVIDENCE_PROVIDER_ROADMAP.md`: the four "Portfolio and account" rows named in step 3, and the
  "Wealth and advisory platforms" and "Tax and accounting tools" rows of "Who would consume this"
- `docs/project/DISCOVERY_WORKBOOK.md`: §20's "Screening and portfolio construction" subsection and §21 only
- `docs/project/milestones/v0.2/api/API_CONTRACT_AND_SLICE_PLAN.md`: the sector line in §4 Out of scope only

## Steps

1. **Commit the spec and file the desktop issue.** Commit this spec as the branch's first commit. Then write the issue
   body below to `.tmp/iad-overview-issue.md` and file it:

   ```text
   gh issue create -R PeterPontbriand/investment-analysis-desktop --title "Overview screen: recent refresh outcomes and watchlists that need attention" --body-file .tmp/iad-overview-issue.md
   ```

   Issue body (each paragraph and list item on one line, as written):

   ```markdown
   ## What

   An overview screen that shows, at a glance, what has happened recently and what needs attention:

   - the most recent refreshes, each with its completion time and its outcome counts as outcome pills, linking to its comparison;
   - the watchlists whose latest refresh has runs that did not complete, each linking to the watchlist.

   ## Why

   Today an investor has to open each watchlist or refresh to learn whether anything went wrong. An overview answers "is everything fine?" in one look, and gives a returning user a natural starting point.

   ## Notes

   - This is not a portfolio dashboard. Holdings, valuation and performance belong to a future portfolio application outside the engine (engine Master Plan §2.5, Product boundaries).
   - Before planning, check whether the engine's existing endpoints already serve what the screen needs; any engine addition is a prerequisite engine slice.
   - Where it sits relative to the planned "Getting started" screen in the sidebar is decided when it is planned.
   - Not scheduled.
   ```

   Check: the command prints the new issue's URL. Record it for the report.

2. **Master Plan §2.5.** In `docs/project/MASTER_PLAN.md`, §2.5 only:

   a. Replace the opening paragraph's first and third sentences, so the paragraph reads:

   ```markdown
   Separate applications divide the work. Each does one job and talks to the others only through a stated route. The engine is this repository; the Investment Analysis Desktop is built in its own repository, and the others are only planned.
   ```

   b. In the table's **Investment Analysis Engine (IAN)** row, "What it must not do" column, replace
   `simulate portfolios or backtests;` with `simulate portfolios or backtests; keep an investor's holdings or
   transactions;`.

   c. Add this row after the **Future predictive evaluator** row:

   ```markdown
   | **Future portfolio application** | Keep an investor's holdings and transactions, value them, track their performance, organize them (classifications, targets) and rebalance toward targets the investor states | Compute an instrument's evidence itself (it asks the engine); recommend trades or place orders; read the engine's database or import its code | Requests evidence from the engine's local HTTP API, passing holdings as request input when an analysis needs them. See [Future portfolio application](#future-portfolio-application) |
   ```

   d. Add this subsection immediately before `### Future MCP adapter`:

   ```markdown
   ### Future portfolio application

   The portfolio application is a planned future application. It is unscheduled, has no repository and has no name yet. Two rules bind it:

   1. Its only route into IAN is the versioned local HTTP API: no database reads and no Python imports.
   2. Holdings stay with it. IAN keeps no record of an investor's holdings or transactions. It receives holdings only as input to a request, for evidence that depends on them, such as look-through aggregation or concentration.

   Open questions, each decided when the work that needs it starts:

   - **Its user interface.** The Investment Analysis Desktop extended to cover it, or a separate GUI application. Both remain options until that decision is taken.
   - **Holdings in saved runs.** Whether a saved Analysis Run of evidence computed from holdings keeps those holdings as its input. Decided when the first such analysis is specified.
   ```

   e. Add this section immediately after the "Decision record: product boundaries (2026-11-01)" section, before
   `## 3. Core Design Principles`:

   ```markdown
   ### Decision record: portfolio application (2026-11-24)

   Approved by the project owner on 2026-11-24.

   - Portfolios belong in a separate [future portfolio application](#future-portfolio-application), not in IAN. Keeping holdings and transactions, valuing them and tracking performance are bookkeeping, not point-in-time evidence, and IAN does not simulate portfolios. The application has no name yet.
   - IAN computes portfolio-level evidence only from holdings supplied with a request: look-through aggregation, issuer concentration and drift against targets the request supplies, and sector-level measures only from a classification the request supplies. IAN chooses no classification scheme ([API plan A.13](milestones/v0.2/api/API_CONTRACT_AND_SLICE_PLAN.md#a13-instrument-profiles-2026-11-20), I9).
   - Wash-sale and superficial-loss windows, and suitability checks, are portfolio-application candidates, not engine scope. The first is bookkeeping on the investor's own trades; the second would apply judgements the project designs itself ([design principle 16](#3-core-design-principles)).
   - Discovery across a universe of instruments (a market scan) is a candidate for a future loop outside IAN, applying the filters an investor states to IAN's evidence for each instrument. Screens and rankings the project would design or validate itself stay with the future predictive evaluator ([decision record of 2026-11-01](#decision-record-product-boundaries-2026-11-01)).
   - No new plan document was created: this section is the record.
   ```

   Check: the documentation checks.

3. **Evidence Provider Roadmap.** In `docs/project/EVIDENCE_PROVIDER_ROADMAP.md`, change only the "Existing plan"
   column of these "Portfolio and account" rows, and leave every other column and row as it is:

   | Row (Strategy) | New "Existing plan" text |
   | :--- | :--- |
   | Look-through aggregation | `New. Engine scope only from holdings supplied with a request; the holdings belong to the future portfolio application ([Product boundaries](MASTER_PLAN.md#25-product-boundaries))` |
   | Concentration and drift | `New. Engine scope only from holdings and targets supplied with a request; sector-level measures only from a classification the request supplies, since the engine chooses no classification scheme ([Product boundaries](MASTER_PLAN.md#25-product-boundaries))` |
   | Tax-rule windows | `Moved to the future portfolio application on 2026-11-24 ([Product boundaries](MASTER_PLAN.md#25-product-boundaries)); not engine scope` |
   | Suitability checks | `Moved to the future portfolio application on 2026-11-24 ([Product boundaries](MASTER_PLAN.md#25-product-boundaries)); not engine scope` |

   In "Who would consume this", change only the second column of two rows:

   | Consumer | New "What they need most" text |
   | :--- | :--- |
   | Wealth and advisory platforms | `Portfolio look-through, concentration and drift, change attribution` |
   | Tax and accounting tools | `Corporate-actions ledger` |

   Check: the documentation checks.

4. **Discovery Workbook.** In `docs/project/DISCOVERY_WORKBOOK.md`:

   a. Replace the body of §20's `### Screening and portfolio construction` subsection (its one paragraph; the heading
   stays) with:

   ```markdown
   An earlier vision had a loop: select analyses, run them, rank and gate the results with a model, then let the person decide. The project no longer plans to own the ranking step. The loop can still be served by applications outside the engine that consume the same evidence, stated-preference filters and Answer Records, with the person deciding ([Product boundaries](MASTER_PLAN.md#25-product-boundaries)):

   - **Discovery.** A future loop could scan a universe of instruments, applying the filters an investor states to the engine's evidence for each one. Screens and rankings the project would design or validate itself belong to the future predictive evaluator.
   - **Portfolios.** A [future portfolio application](MASTER_PLAN.md#future-portfolio-application) keeps the investor's holdings, tracks their performance and rebalances toward the investor's targets, asking the engine for evidence about each instrument and about holdings it supplies.
   ```

   b. In §21 Non-Goals, add this bullet immediately after the first bullet (the GUI one):

   ```markdown
   - Keeping an investor's holdings or transactions. A [future portfolio application](MASTER_PLAN.md#future-portfolio-application) keeps them.
   ```

   Check: the documentation checks.

5. **API contract plan.** In `docs/project/milestones/v0.2/api/API_CONTRACT_AND_SLICE_PLAN.md`, §4 Out of scope, replace
   the end of the sector bullet. The bullet currently ends:

   ```text
   a portfolio-organization judgement that belongs to a future portfolio analysis and rebalancing feature set outside the
   engine (A.13 link, I9).
   ```

   Change it to end, keeping the existing A.13 link and the file's line wrapping style:

   ```text
   a portfolio-organization judgement that belongs to the future portfolio application (linked to
   ../../../MASTER_PLAN.md#future-portfolio-application), outside the engine (A.13 link, I9).
   ```

   Leave A.13 and its I9 row unchanged.

   Check: the documentation checks.

6. **Finish.** Run the documentation checks once more, commit with the PR text's title, push the branch, and report.
   After the spec author's clean review, open the pull request with the PR text.

## Norms and safeguards

- Escalate by the table in [`AGENTS.md` §11](../../../AGENTS.md#escalation-in-a-spec-driven-unit).
- Filing the desktop issue in step 1 is approved by the project owner (B12). It is the only GitHub action beyond pushing
  the branch and opening its pull request.
- Documentation-only change: the documentation checks are those
  [Quality gates](../README.md#quality-gates) names for a documentation-only change. No served document changes, so
  the served-content commands do not apply; if a check says otherwise, escalate.
- No name for the portfolio application anywhere (B11), including in commit messages and the PR text.
- No AI or tool attribution in commits, the issue or the PR text.
- Where an exact text in a step no longer matches `main` (for example a sentence was reworded since `4e82469`),
  escalate rather than adapt it.

## Acceptance checks

- The documentation checks pass: `python scripts/check_doc_links.py`, `python scripts/check_help_content.py`,
  `python scripts/check_sequence_tables.py`, `python scripts/check_package_dependencies.py`, `uv run ruff check .` and
  `uv run ruff format --check .`.
- `git grep -n "Three applications" -- docs` prints nothing.
- `git grep -n "portfolio analysis and rebalancing feature set" -- docs ':!docs/project/specs'` prints exactly one
  line: A.13's I9 row in `API_CONTRACT_AND_SLICE_PLAN.md`, which stays as written (B9). The spec is excluded because
  step 5 quotes the old text.
- `git grep -n -i -e "P[M]N" -e "Portfolio [M]anagement Engine" -- docs` prints nothing. The brackets keep the
  pattern from matching this line.
- `git grep -n "future-portfolio-application" -- docs` lists links in `MASTER_PLAN.md`, `DISCOVERY_WORKBOOK.md` and
  `API_CONTRACT_AND_SLICE_PLAN.md`.
- `git --no-pager diff --stat origin/main...HEAD` lists only the allowed files.
- The desktop issue exists, with the title and body of step 1.

## Report

- The commit hash and `git --no-pager diff --stat origin/main...HEAD`.
- The result of each documentation check, and of each acceptance check.
- The desktop issue's URL.
- Every escalation, with the `AGENTS.md` §11 table row that triggered it.
- Pilot measures: one value per measure in the [spec workflow §7](../SPEC_WORKFLOW.md#7-pilot).

## PR text

Title: `docs(boundaries): record the future portfolio application and settle portfolio scope`

Description:

```markdown
Records where portfolios belong in the suite and removes the contradictions between the planning documents.

- Master Plan §2.5 (Product boundaries): a future portfolio application keeps an investor's holdings and transactions; the engine keeps none and computes portfolio-level evidence only from holdings supplied with a request. New row, a "Future portfolio application" subsection with its rules and open questions, and a 2026-11-24 decision record. The opening no longer states a count of applications.
- Evidence Provider Roadmap: the "Portfolio and account" rows say which parts are engine scope; wash-sale windows and suitability checks move to the portfolio application.
- Discovery Workbook: §20 names the discovery loop and the portfolio application; §21 adds keeping holdings as a non-goal.
- API contract plan §4: the sector line links to the portfolio application.

Spec: `docs/project/specs/portfolio-application-boundary.md`. Documentation only.
```

## Change log

- 2026-11-24: acceptance checks on the old sector wording and on the working name corrected. The old wording
  legitimately remains in A.13's I9 row (B9) and in step 5's quotation, and the working-name check matched its own
  pattern in this spec; both checks now say exactly what they expect.
