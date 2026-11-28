# Spec Issue 310: served guides in investor words

- **Owning plan:** [API plan](../API_CONTRACT_AND_SLICE_PLAN.md), sequence row `Issue 310` and decision record A.23, both
  written by step 1 of this spec.
- **Branch:** `docs/investor-guide-wording`, from `main` at `a48c274` (`docs(ph): investor glossary in investor words
  (issue 305) (#311)`).
- **Decisions approved:** 2026-11-27, by the project owner (decisions H1 to H10 of the served-guides decision list).
- **Lane:** normal.

## Goal

The served guides speak about markets, companies, data and methods, never about this project's machinery: no
"Investment Analysis Engine", "the engine", "provider" or "data provider" in any served section of the Beginner Guide,
Finance Math or a strategy guide, links to renamed glossary terms show the new names, Finance Math says exactly what it
said before in investor words, and the help-content check keeps it so for every served page.

## Decisions

Each line is recorded verbatim, with its approval date, in record A.23 by step 1.

- **H1** Recorded in the API plan as sequence row `Issue 310` (Next, above API.24, which becomes Planned) and record
  A.23; this spec; branch `docs/investor-guide-wording`; closes #310.
- **H2** Scope: the served sections of the Beginner Guide, Finance Math and every strategy guide (titles,
  introductions, prose, tables, fenced text blocks, link texts). Excluded sections and the glossary are not changed.
- **H3** "Investment Analysis Engine" and "the engine" become "this application", or are removed; "a/the provider" and
  "data provider" become "a/the data source", or the source's name. Code values in backticks stay.
- **H4** "the Yahoo adapter", "production tool boundary", "current production ... mapping/analysis" and "resolver" are
  replaced too, as step 2's table says; they are not added to the check.
- **H5** The Beginner Guide's "the project" and "the program", where they mean the software, become "this application";
  its title becomes "A Beginner's Guide to Investment Analysis". Headings that carry a section id keep their wording.
- **H6** Link texts that repeat a term name renamed by #305 take the new name; destinations do not change.
- **H7** Finance Math changes wording only; every changed line is in step 2's table.
- **H8** The FCF Growth presenter's `Provider split adjustments applied:` label becomes
  `Split adjustments in the price history applied:` (both forms), with its test.
- **H9** `scripts/check_help_content.py` refuses the whole words "engine" and "provider" (any case, plurals) in every
  served section outside the user glossary: title and lines, fenced blocks included, outside code spans and link
  destinations; excluded sections are not checked; no allow list.
- **H10** No API shape or version change: document, section and term ids and code values stay; the help bundle is
  regenerated; no desktop issue.

## Out of scope

- The user glossary, the contributor glossary, and every excluded section of a served document (for example the
  strategy guides' command-line sections and the Beginner Guide's "First steps after this guide").
- Headings that carry a section id, including the Beginner Guide's "How the project applies this model today" and
  "What the project does not establish": their wording and ids stay (H5, H10).
- Any message produced by code other than H8's label, including the FCF yield warning's wording and every "data
  provider" message (API.24, issue #306).
- Code identifiers and code values, such as `provider_adjustments`, `provider_failure`, `provider_error` and
  `provider_no_data`.
- `docs/user/API.md`, `USAGE.md` and any other document the help bundle does not serve.
- Any change to what a sentence claims beyond the wording this spec gives; a sentence whose meaning seems wrong is
  reported, not fixed.
- Any schema, OpenAPI document, API version or `schema_version`; the desktop repository.

## Allowed files

- `docs/project/milestones/v0.2/api/specs/issue-310.md` (this spec).
- `docs/project/milestones/v0.2/api/API_CONTRACT_AND_SLICE_PLAN.md`: §2's rows `Issue 310` and `API.24`, the new §3
  section, the new record A.23 in Appendix A.
- `docs/user/BEGINNER_GUIDE.md`, `docs/user/FINANCE_MATH.md`, `docs/user/strategies/FCF_GROWTH.md`,
  `docs/user/strategies/GRAHAM_GROWTH.md`, `docs/user/strategies/GRAHAM_NUMBER.md`,
  `docs/user/strategies/MOMENTUM.md`: the lines of step 2's table only.
- `investment_analysis_engine/strategies/fcf_growth/presenter.py`: the two label lines of step 3 only.
- `tests/reporting/test_fcf_growth_market_cap_presentation.py`: the three assertions of step 3 only.
- `docs/project/README.md`: the "Served documents" section, one new bullet (step 4).
- `scripts/check_help_content.py`
- `tests/scripts/test_check_help_content.py`
- `investment_analysis_engine/help/help_bundle.en.json` (regenerated only).
- Any other test file that fails only because it pins a guide sentence or the label this spec changes: listed by name
  in the report. Any other failure is an escalation.

## Steps

1. **Spec and records.** Commit this spec as the branch's first commit. Then, in one commit, in the API plan:
   - §2: add row `| Issue 310 | [Served guides in investor words](#issue-310--served-guides-in-investor-words) | Next | |`
     directly above the `API.24` row, and change `API.24`'s status from `Next` to `Planned`.
   - §3, after the `Issue 305` section and before `## 4. Out of scope`, a new section:

     ```markdown
     ### Issue 310 — Served guides in investor words

     - **Problem:** the served guides (the Beginner Guide, Finance Math and the strategy guides) speak about this
       project's machinery ("Investment Analysis Engine", "the engine", "the provider", "the Yahoo adapter", "the
       resolver"), and links to renamed glossary terms still show the old names (engine issue 310).
     - **Decision:** served sections use "this application" and "data source", wording only in Finance Math; the FCF
       Growth split-adjustment output label is renamed to match; the help-content check refuses "engine" and "provider"
       in every served section ([A.23](#a23-served-guides-in-investor-words-2026-11-27), H1 to H10).
     - **Scope:** the served sections of the Beginner Guide, Finance Math and the strategy guides, one presenter label
       and its test, the served-documents rules in the project README, `scripts/check_help_content.py` and its tests, the
       regenerated help bundle.
     - **Branch:** `docs/investor-guide-wording`.
     - **Detail:** this unit's spec: [specs/issue-310.md](specs/issue-310.md); decisions in
       [A.23](#a23-served-guides-in-investor-words-2026-11-27).
     ```

   - Appendix A, after A.22 (the end of the file): the record under [Record to add](#record-to-add) below, verbatim.
   - Check: the documentation checks (`python scripts/check_doc_links.py`, `python scripts/check_sequence_tables.py`,
     `python scripts/check_package_dependencies.py`, `uv run ruff check .`, `uv run ruff format --check .`).
2. **Guide rewrite (H2 to H7).** Line numbers are those of each file at `a48c274`. Each row replaces its Replace text,
   which occurs exactly once on that line, with its With text. Both are written inside a double-backtick code span:
   the text is what lies between the delimiters, without the one space on each side, and `\|` in it is a literal `|`.
   A line with several rows takes them in order. Every other word of the line, every link destination and every line
   not listed stays as it is. A row whose Replace text is not found exactly once on its line is an escalation, never a
   guess.

   **`docs/user/BEGINNER_GUIDE.md`**

   | Line | Replace | With |
   | :--- | :--- | :--- |
   | 1 | `` # A Beginner's Guide to Investment Analysis in This Project `` | `` # A Beginner's Guide to Investment Analysis `` |
   | 3 | `` start exploring Investment Analysis Engine. `` | `` start exploring this application. `` |
   | 11 | `` You give the program a `` | `` You give this application a `` |
   | 16 | `` - **Data provider:** a service the program gets information from. This project uses `` | `` - **Data source:** a service this application gets information from. It uses `` |
   | 24 | `` In this project, **quantitative** `` | `` Here, **quantitative** `` |
   | 24 | `` The project's software performs financial arithmetic `` | `` This application performs financial arithmetic `` |
   | 32 | `` The project selects and prepares `` | `` This application selects and prepares `` |
   | 45 | `` using the project's [Graham Number] `` | `` using the [Graham Number] `` |
   | 59 | `` the project uses reported diluted EPS `` | `` this application uses reported diluted EPS `` |
   | 61 | `` The project derives BVPS `` | `` This application derives BVPS `` |
   | 63 | `` If the project has a current share price `` | `` If this application has a current share price `` |
   | 77 | `` strategy, the project calculates `` | `` strategy, this application calculates `` |
   | 77 | `` for the project's calculation and limits `` | `` for the calculation and its limits `` |
   | 85 | `` the time the project retrieves it `` | `` the time this application retrieves it `` |
   | 87 | `` In this project's [Graham Growth Value] `` | `` In the [Graham Growth Value] `` |
   | 87 | `` the project does not currently provide `` | `` this application does not currently provide `` |
   | 103 | `` A few of the project's strategies `` | `` A few of this application's strategies `` |
   | 109 | `` as the project grows `` | `` as this application grows `` |
   | 113 | `` the project uses [SEC filings] `` | `` this application uses [SEC filings] `` |
   | 115 | `` The project uses a software component called `` | `` This application uses a software component called `` |
   | 119 | `` The project's [`as_of`] `` | `` The [`as_of`] `` |
   | 125 | `` Investment Analysis Engine does not provide `` | `` This application does not provide `` |
   | 125 | `` [project limitations and disclaimer] `` | `` [limitations and disclaimer] `` |

   **`docs/user/FINANCE_MATH.md`**

   | Line | Replace | With |
   | :--- | :--- | :--- |
   | 3 | `` that Investment Analysis Engine currently implements. `` | `` that this application currently implements. `` |
   | 5 | `` the project may someday support `` | `` this application may someday support `` |
   | 11 | `` Investment Analysis Engine uses different sources `` | `` This application uses different sources `` |
   | 23 | `` A provider that supplies a current quote `` | `` A data source that supplies a current quote `` |
   | 30 | `` configured data provider `` | `` configured data source `` |
   | 53 | `` A data provider that answers `` | `` A data source that answers `` |
   | 53 | `` it is not an error of the provider. `` | `` it is not an error of the data source. `` |
   | 53 | `` and its reason names the provider: `` | `` and its reason names the data source: `` |
   | 53 | `` A provider that did not answer, was limiting requests or answered in a form the engine does not read `` | `` A data source that did not answer, was limiting requests or answered in a form this application does not read `` |
   | 140 | `` the same provider concept `` | `` the same reported concept `` |
   | 140 | `` Provider-exposed share-class and split-treatment evidence must agree. `` | `` Share-class and split-treatment evidence reported by the data source must agree. `` |
   | 150 | `` A provider-reported BVPS `` | `` A BVPS reported by a data source `` |
   | 150 | `` Investment Analysis Engine's SEC calculation derives `` | `` The SEC EDGAR calculation derives `` |
   | 156 | `` set aside and the provider asked once. `` | `` set aside and the data source asked once. `` |
   | 196 | `` by default, for every provider. The production tool boundary also supports an explicit single completed fiscal-year EPS basis for reviewed workflows. `` | `` by default, for every data source. An explicit single completed fiscal-year EPS basis is also supported for reviewed workflows. `` |
   | 207 | `` set aside and the provider asked once. `` | `` set aside and the data source asked once. `` |
   | 263 | `` a provider quote may not. Provider quotes without verified currency `` | `` a quote from a data source may not. Quotes from a data source without verified currency `` |
   | 271 | `` Investment Analysis Engine does not impose `` | `` This application does not impose `` |
   | 290 | `` because providers may report cash outflows `` | `` because data sources may report cash outflows `` |
   | 290 | `` The normalization and original provider field remain in provenance. `` | `` The normalization and the data source's original field remain in provenance. `` |
   | 292 | `` For each company the engine uses one of the two `` | `` For each company the analysis uses one of the two `` |
   | 294 | `` A provider's precomputed “free cash flow” `` | `` A data source's precomputed “free cash flow” `` |
   | 345 | `` The current production SEC mapping may not supply analyst consensus `` | `` SEC EDGAR data may not include analyst consensus `` |
   | 397 | `` after a provider failure other than an absent answer `` | `` after a data source failure other than an absent answer `` |
   | 397 | `` when the provider answered with nothing `` | `` when the data source answered with nothing `` |
   | 397 | `` for a provider-confirmed ETF `` | `` for an ETF that the data source confirms as one `` |
   | 419 | `` ratios of the provider split adjustments `` | `` ratios of the split adjustments in the price history `` |
   | 425 | `` - **Provider split adjustments:** `` | `` - **Split adjustments in the price history:** `` |
   | 425 | `` the date up to which the provider adjusted the price. The provider's split history `` | `` the date up to which the data source adjusted the price. The data source's split history `` |
   | 425 | `` it undoes the provider's adjustment of the historical close `` | `` it undoes the data source's adjustment of the historical close `` |
   | 495 | `` Investment Analysis Engine does not currently retrieve it automatically. `` | `` this application does not currently retrieve it automatically. `` |

   **`docs/user/strategies/FCF_GROWTH.md`**

   | Line | Replace | With |
   | :--- | :--- | :--- |
   | 7 | `` a later resolver clock cannot admit later filings into an earlier execution boundary. `` | `` filings made after that time are never admitted into an analysis at an earlier date. `` |
   | 74 | `` When a market-data provider fails, the warning names the provider and the kind of failure (such as `yfinance` and `rate_limited`) and never repeats the provider's own message. `` | `` When a market-data source fails, the warning names the source and the kind of failure (such as `yfinance` and `rate_limited`) and never repeats the source's own message. `` |
   | 74 | `` The failure is not recorded as a provider failure of the run. `` | `` The failure is not recorded as a data source failure of the run. `` |
   | 83 | ``   Provider split adjustments applied: `` | ``   Split adjustments in the price history applied: `` |
   | 97 | `` - The provider's split history reports splits and other adjustments alike. A provider adjustment for a spin-off `` | `` - The data source's split history reports splits and other adjustments alike. An adjustment for a spin-off `` |
   | 97 | `` which the provider applied to the historical close `` | `` which the data source applied to the historical close `` |
   | 126 | `` and the engine does not convert them. `` | `` and they are not converted. `` |
   | 188 | `` Forward estimates are optional provider evidence, not predictions generated by Investment Analysis Engine. The current production SEC EDGAR mapping supplies historical company facts but may not supply forward analyst consensus. `` | `` Forward estimates are optional evidence from a data source, not predictions generated by this application. SEC EDGAR data supplies historical company facts but may not include forward analyst consensus. `` |
   | 226 | `` The current production analysis resolves annual financial facts from SEC EDGAR. `` | `` The analysis takes annual financial facts from SEC EDGAR. `` |
   | 247 | `` does not accept a provider's precomputed `` | `` does not accept a data source's precomputed `` |
   | 247 | `` retains their provider fields, `` | `` retains their source fields, `` |
   | 249 | `` The resolver rejects incompatible facts `` | `` The analysis rejects incompatible facts `` |
   | 263 | `` Investment Analysis Engine preserves the reported annual history `` | `` This application preserves the reported annual history `` |

   **`docs/user/strategies/GRAHAM_GROWTH.md`**

   | Line | Replace | With |
   | :--- | :--- | :--- |
   | 3 | `` how the Investment Analysis Engine ** `` | `` how the ** `` |
   | 48 | `` The engine never steps back to an older year `` | `` The analysis never steps back to an older year `` |
   | 52 | `` the engine asks the provider again, once, `` | `` the data source is asked again, once, `` |
   | 76 | `` Investment Analysis Engine shows how far `` | `` this application shows how far `` |
   | 89 | `` filings, provider failures, and explicit `` | `` filings, data source failures, and explicit `` |
   | 166 | `` rather than being presented as provider-verified evidence. `` | `` rather than being presented as evidence from a data source. `` |
   | 186 | `` Investment Analysis Engine currently uses eligible SEC filing facts `` | `` This application currently uses eligible SEC filing facts `` |
   | 194 | `` Investment Analysis Engine obtains current quote data `` | `` this application obtains current quote data `` |
   | 198 | `` which the current Yahoo adapter does not supply. `` | `` which Yahoo Finance does not supply. `` |
   | 215 | `` Current-only quote providers do not manufacture historical quotes. `` | `` Data sources of current quotes only do not manufacture historical quotes. `` |
   | 239 | `` (the default, for every provider) `` | `` (the default, for every data source) `` |
   | 260 | `` Provider corrections, accounting restatements `` | `` Data source corrections, accounting restatements `` |
   | 262 | `` make Investment Analysis Engine's formula, `` | `` make this application's formula, `` |
   | 281 | `` the data provider has no value `` | `` the data source has no value `` |
   | 282 | `` or the provider gave no date `` | `` or the data source gave no date `` |
   | 284 | `` so the engine does not combine them. `` | `` so they are not combined. `` |
   | 287 | `` [Provider error](../GLOSSARY.md#status-provider-error) (`provider_error`): the data provider could not be reached `` | `` [Data source error](../GLOSSARY.md#status-provider-error) (`provider_error`): the data source could not be reached `` |
   | 289 | `` none came from a data provider, `` | `` none came from a data source, `` |

   **`docs/user/strategies/GRAHAM_NUMBER.md`**

   | Line | Replace | With |
   | :--- | :--- | :--- |
   | 3 | `` how the Investment Analysis Engine ** `` | `` how the ** `` |
   | 30 | `` Investment Analysis Engine describes the result `` | `` This application describes the result `` |
   | 46 | `` data, Investment Analysis Engine derives BVPS `` | `` data, this application derives BVPS `` |
   | 52 | `` The engine never steps back to an older year `` | `` The analysis never steps back to an older year `` |
   | 56 | `` the engine asks the provider again, once, `` | `` the data source is asked again, once, `` |
   | 66 | `` Investment Analysis Engine shows how far `` | `` this application shows how far `` |
   | 79 | `` filings, provider failures, and explicit `` | `` filings, data source failures, and explicit `` |
   | 149 | `` rather than being presented as provider-verified evidence. `` | `` rather than being presented as evidence from a data source. `` |
   | 169 | `` Investment Analysis Engine currently uses eligible SEC filing facts for: `` | `` This application currently uses eligible SEC filing facts for: `` |
   | 183 | `` Investment Analysis Engine obtains current quote data `` | `` this application obtains current quote data `` |
   | 187 | `` which the current Yahoo adapter does not supply. `` | `` which Yahoo Finance does not supply. `` |
   | 204 | `` Current-only quote providers do not manufacture historical quotes. `` | `` Data sources of current quotes only do not manufacture historical quotes. `` |
   | 228 | `` Investment Analysis Engine uses three-year-average diluted EPS `` | `` This application uses three-year-average diluted EPS `` |
   | 244 | `` Investment Analysis Engine uses a documented common-equity `` | `` This application uses a documented common-equity `` |
   | 260 | `` Provider corrections, accounting restatements `` | `` Data source corrections, accounting restatements `` |
   | 262 | `` make Investment Analysis Engine's formula, `` | `` make this application's formula, `` |
   | 281 | `` the data provider has no value `` | `` the data source has no value `` |
   | 282 | `` or the provider gave no date `` | `` or the data source gave no date `` |
   | 284 | `` so the engine does not combine them. `` | `` so they are not combined. `` |
   | 287 | `` [Provider error](../GLOSSARY.md#status-provider-error) (`provider_error`): the data provider could not be reached `` | `` [Data source error](../GLOSSARY.md#status-provider-error) (`provider_error`): the data source could not be reached `` |
   | 289 | `` none came from a data provider, `` | `` none came from a data source, `` |

   **`docs/user/strategies/MOMENTUM.md`**

   | Line | Replace | With |
   | :--- | :--- | :--- |
   | 3 | `` This guide explains the Investment Analysis Engine **Momentum Strategy** `` | `` This guide explains the **Momentum Strategy** `` |
   | 56 | `` retains original provider retrieval time and cache origin. Historical daily labels are not verified exchange-close timestamps, and the provider's past adjusted-price vintages `` | `` retains the data source's original retrieval time and cache origin. Historical daily labels are not verified exchange-close timestamps, and the data source's past adjusted-price vintages `` |
   | 73 | `` keeps the exact instants its provider supplied. `` | `` keeps the exact instants its data source supplied. `` |
   | 75 | `` The one exception is a provider that stamps `` | `` The one exception is a data source that stamps `` |
   | 77 | `` Provider-adjusted prices are revised retroactively `` | `` Prices adjusted by the data source are revised retroactively `` |
   | 149 | `` \| The price provider failed \| `` | `` \| The price data source failed \| `` |
   | 151 | `` A provider failure never stores the provider's own error text: the stored reason is a fixed message, and `provider_failure` names the provider and the kind of failure. `` | `` A data source failure never stores the data source's own error text: the stored reason is a fixed message, and `provider_failure` names the data source and the kind of failure. `` |
   | 179 | `` or provider histories. `` | `` or data source histories. `` |

   Check: `python scripts/check_help_content.py` still passes (the new rule comes in step 5), then the documentation
   checks.
3. **The split-adjustment label (H8).** In `investment_analysis_engine/strategies/fcf_growth/presenter.py`, function
   `_market_cap_detail_lines`, change `"  Provider split adjustments applied:"` to
   `"  Split adjustments in the price history applied:"` and `"  Provider split adjustments applied: none"` to
   `"  Split adjustments in the price history applied: none"`. In
   `tests/reporting/test_fcf_growth_market_cap_presentation.py`, change the same two strings in its three assertions
   (lines 60, 208 and 209 at `a48c274`). Nothing else in either file changes, including the field
   `provider_adjustments`. Check: `uv run pytest tests/reporting/test_fcf_growth_market_cap_presentation.py -q`.
4. **The rule in the README (H9).** In `docs/project/README.md`, section "Served documents", directly after the
   "Leak rules" bullet, add:

   ```markdown
   - **Investor wording:** a served section speaks about markets, companies, data and methods, not about this software. Its title and text, fenced blocks included, outside code spans and link destinations, never use the words engine or provider: write this application where its behavior matters to an investor, and data source, or the source's name, for where data comes from. `python scripts/check_help_content.py` fails otherwise; the glossary's own rule is under Glossary entries.
   ```

   Check: the documentation checks.
5. **The check (H9).** In `scripts/check_help_content.py`:
   - After `_WORDING_RULE_SEE`, a constant `_SERVED_RULE_SEE = "; see docs/project/README.md, Served documents"`.
   - After `_section_problems`, the function under [Code to add](#code-to-add), verbatim.
   - In `check_served_content`, in the loop over each document's sections, after
     `problems.extend(_section_problems(section, document.path, context))`, add
     `if document.path != USER_GLOSSARY: problems.extend(_served_wording_problems(section, document.path))` (two
     lines, formatted by Ruff). The user glossary is left to the glossary rule, so a word is never reported twice.
   - The module docstring, after the list of what served content fails on, gains the paragraph: "Outside the user
     glossary, whose entries the glossary rules cover, a served section's title and lines, fenced blocks included,
     never use the whole words engine or provider outside code spans and link destinations."
   - In `tests/scripts/test_check_help_content.py`, directly above `class TestExcludedSections`, the class
     `TestServedWording` under [Code to add](#code-to-add), verbatim.
   - Check: slice check.
6. **Help bundle (H10).** Run `uv run python -m scripts.generate_help`. Document ids, section ids, group ids and term
   ids must be unchanged; only text and the Beginner Guide's title change. Check: slice check.
7. **Close the row.** In the API plan §2, set `Issue 310`'s status to `Complete` with today's date in Completed, and
   set `API.24` to `Next` (AGENTS.md §12). Check: the documentation checks.
8. **Finish.** Run the slice check once, commit with the PR text's title, push the branch
   (`git push -u origin docs/investor-guide-wording`) and report. Do not open the pull request until the spec
   author's review is clean; then open it with the PR text below and assign it to the project owner.

## Code to add

The function for step 5, placed after `_section_problems`:

```python
def _served_wording_problems(section: ServedSection, relative_path: str) -> list[ContentProblem]:
    """Return the internal words a served section's heading and lines use, one problem per distinct word on a line.

    Code spans, link destinations and id lines are not read; fenced blocks are.
    """
    lines = [(section.first_line, section.heading)]
    lines.extend((section.body_first_line + offset, raw) for offset, raw in enumerate(section.lines))
    found: list[ContentProblem] = []
    for number, raw in lines:
        if ANCHOR_ID_RE.match(raw.strip()):
            continue
        searchable = _LINK_DESTINATION_RE.sub(r"\1", _INLINE_CODE_RE.sub(" ", raw))
        words = sorted({match.group(0).lower() for match in INVESTOR_FORBIDDEN_WORDS_RE.finditer(searchable)})
        found.extend(
            ContentProblem(relative_path, number, section.heading, f"uses the internal word '{word}'{_SERVED_RULE_SEE}")
            for word in words
        )
    return found
```

The test class for step 5:

```python
class TestServedWording:
    def test_a_word_in_prose_is_reported_with_its_line_and_section(self, tmp_path: Path) -> None:
        problems = served_problems("# G\n\n## Sec\n\nThe engine reads it.\n", tmp_path)
        assert problems == [
            f"{GUIDE}:5: section 'Sec' -- uses the internal word 'engine'; see docs/project/README.md, Served documents"
        ]

    def test_a_title_heading_and_table_are_checked(self, tmp_path: Path) -> None:
        guide = "# Engine guide\n\n## Provider notes\n\n| Case | Code |\n| :--- | :--- |\n| Provider failed | x |\n"
        problems = served_problems(guide, tmp_path)
        assert [problem.split(" -- ")[0] for problem in problems] == [
            f"{GUIDE}:1: section 'Engine guide'",
            f"{GUIDE}:3: section 'Provider notes'",
            f"{GUIDE}:7: section 'Provider notes'",
        ]

    def test_plurals_and_capitals_are_reported_once_per_word_and_line(self, tmp_path: Path) -> None:
        problems = served_problems("# G\n\n## S\n\nEngines and PROVIDERS, the provider.\n", tmp_path)
        assert len(problems) == 3
        assert {problem.rsplit("'", 2)[1] for problem in problems} == {"engines", "providers", "provider"}

    def test_a_fenced_block_is_checked(self, tmp_path: Path) -> None:
        problems = served_problems("# G\n\n## S\n\n```text\nProvider split adjustments applied:\n```\n", tmp_path)
        assert len(problems) == 1
        assert ":6: " in problems[0]

    def test_code_spans_link_destinations_and_link_texts(self, tmp_path: Path) -> None:
        clean = "# G\n\n## S\n\nCode `provider_error`, [error](../GLOSSARY.md#cache), see [it](https://example.com/engine).\n"
        assert served_problems(clean, tmp_path) == []
        problems = served_problems("# G\n\n## S\n\n[Provider error](../GLOSSARY.md#cache).\n", tmp_path)
        assert len(problems) == 1
        assert "'provider'" in problems[0]

    def test_an_excluded_section_passes(self, tmp_path: Path) -> None:
        guide = f"# G\n\n## Data\n\nText.\n\n### On the command line\n{EXCLUDE_MARKER}\n\nThe engine and provider.\n"
        assert served_problems(guide, tmp_path) == []

    def test_only_whole_words_are_reported(self, tmp_path: Path) -> None:
        assert served_problems("# G\n\n## S\n\nProvidential engineering.\n", tmp_path) == []

    def test_a_glossary_entry_is_left_to_the_glossary_rule(self, tmp_path: Path) -> None:
        glossary = "# Glossary\n\n## Terms\n\n" + entry("cache", "Cache", "Kept by the engine.") + entry("eps", "EPS")
        problems = served_problems("# G\n\nText.\n", tmp_path, {USER_GLOSSARY: glossary})
        assert problems == []
```

## Norms and safeguards

- The [escalation table in AGENTS.md §11](../../../../../../AGENTS.md#escalation-in-a-spec-driven-unit) applies.
- No attribution of any kind (AGENTS.md §3), no new dependency, no change to `pyproject.toml` or `uv.lock`.
- Finance Math is the formula authority (AGENTS.md §8): its only changes are the rows of step 2's table. A formula,
  condition, number, reason code or status that would read differently is an escalation.
- Ids, anchors, link destinations, headings that carry a section id, code values and field names never change.
- A word the new check finds that step 2's table misses is an escalation to the spec author; never settled in a guide.
- Issue #116 evidence: stop and keep the run directory (AGENTS.md §10).

## Acceptance checks

1. Slice check passes: the wrapper's closing summary shows every step passed.
2. No served section uses the words: `python scripts/check_help_content.py` exits 0, and
   `uv run pytest tests/scripts/test_check_help_content.py tests/scripts/test_served_content.py -q` passes, including
   `TestServedWording`.
3. Finance Math changed only on the table's lines:
   `git --no-pager diff --unified=0 origin/main...HEAD -- docs/user/FINANCE_MATH.md | grep -E '^@@'` lists exactly
   lines 3, 5, 11, 23, 30, 53, 140, 150, 156, 196, 207, 263, 271, 290, 292, 294, 345, 397, 419, 425 and 495, each as a
   one-line change.
4. Bundle ids unchanged:
   `uv run python -c "import json,subprocess;old=json.loads(subprocess.run(['git','show','origin/main:investment_analysis_engine/help/help_bundle.en.json'],capture_output=True,text=True,encoding='utf-8',check=True).stdout);new=json.load(open('investment_analysis_engine/help/help_bundle.en.json',encoding='utf-8'));ids=lambda b:(sorted(b['terms']),sorted(b['documents']),{k:[s['id'] for s in v['sections']] for k,v in b['documents'].items()});print(ids(old)==ids(new))"`
   prints `True`.
5. The new title is served:
   `uv run python -c "import json;print(json.load(open('investment_analysis_engine/help/help_bundle.en.json',encoding='utf-8'))['documents']['beginner-guide']['title'])"`
   prints `A Beginner's Guide to Investment Analysis`.
6. `uv run python -m scripts.generate_help --check` passes.
7. `git --no-pager diff --stat origin/main...HEAD` lists only allowed files.

## Report

The final commit hash; the diff stat; the last slice-check result with its `gate-output.txt` path; the result of each
acceptance check; any test file changed under the last allowed-files line, with why; every escalation with the
table row that triggered it; and "Pilot measures: escalations N, of which spec defects N; owner actions N".

## PR text

Title: `docs(ph): served guides in investor words (issue 310)`

```markdown
## Summary

The Beginner Guide, Finance Math and the strategy guides now speak about markets, companies, data and methods instead
of this project's machinery, as the glossary has since #305.

## User-visible changes

- The served guides say "this application" and "data source" instead of "Investment Analysis Engine", "the engine"
  and "provider", and no longer mention adapters, resolvers or production mappings.
- Links to the data-source status terms show their new names, such as "Data source error".
- The Beginner Guide's title is now "A Beginner's Guide to Investment Analysis".
- Finance Math changes wording only; no formula, rule or reason code changes.
- The FCF Growth market-capitalization notes print "Split adjustments in the price history applied:" instead of
  "Provider split adjustments applied:".
- The help bundle is regenerated. No API shape, document, section or term id, code value or version changes.

## For contributors

- `scripts/check_help_content.py` refuses the words "engine" and "provider" in every served section outside code
  spans and link destinations, fenced blocks included; the rule is in `docs/project/README.md`, "Served documents".

## Records

- API plan: row Issue 310 and record A.23. Messages produced by code are reworded by API.24 (#306), which is next.

Closes #310
```

## Record to add

Step 1 appends this record to the API plan's Appendix A, after A.22, exactly as written here.

```markdown
### A.23 Served guides in investor words (2026-11-27)

Approved by the project owner on 2026-11-27, as decisions H1 to H10. Closes engine issue 310, which follows engine
issue 305 ([A.22](#a22-investor-glossary-wording-2026-11-27), G8).

| # | Decision |
| :--- | :--- |
| H1 | Recorded in this plan as sequence row Issue 310 and this record; the unit's spec is `specs/issue-310.md`, its branch `docs/investor-guide-wording`. API.24 stays Planned until this unit completes. |
| H2 | Scope: the served sections of the Beginner Guide, Finance Math and every strategy guide: titles, introductions, prose, tables, fenced text blocks and link texts. Excluded command-line sections are not changed. The glossary is not touched. |
| H3 | The words of G3: "Investment Analysis Engine" and "the engine" become "this application" where the behavior matters to an investor and are removed where it does not; "a/the provider" and "data provider" become "a/the data source", or the source's name (SEC EDGAR, Yahoo Finance). Code values in backticks, such as `provider_error`, `provider_no_data` and `provider_failure`, stay. |
| H4 | Other internal words in served text are replaced too, line by line in the spec: "the Yahoo adapter" becomes Yahoo Finance; "production tool boundary", "current production SEC EDGAR mapping" and "current production analysis" become plain statements of what the analysis does; "the resolver" and "resolver clock" become "the analysis" or the as-of rule in investor words. They are not added to the check: they are rare, and "production" has ordinary uses. |
| H5 | Where "the project" or "the program" means the software in the Beginner Guide, it becomes "this application"; the guide's title becomes "A Beginner's Guide to Investment Analysis", and the README link's text becomes "limitations and disclaimer". Finance Math's "the project may someday support" becomes "this application". Headings that carry a section id keep their wording, so section ids do not change. "Project" is not added to the check. |
| H6 | Link texts that repeat a term name renamed by G4 take the new name ("Provider error" becomes "Data source error"); link destinations and anchors do not change. |
| H7 | Finance Math changes wording only: no formula, condition, threshold, ratio, date rule, reason code or status changes meaning. The spec lists every changed Finance Math line before and after, and the review compares Finance Math with that list. "Provider concept" becomes "reported concept"; "Provider split adjustments" becomes "Split adjustments in the price history". |
| H8 | The command line's `Provider split adjustments applied:` (and its `: none` form) becomes `Split adjustments in the price history applied:` in the FCF Growth presenter and its test, so the FCF Growth guide's sample output and Finance Math keep matching the output. Every other message produced by code stays with API.24 ([A.21](#a21-explain-why-a-result-has-no-number-2026-11-25), C27; [A.22](#a22-investor-glossary-wording-2026-11-27), G9). |
| H9 | `scripts/check_help_content.py` extends G7 from investor glossary entries to every served section outside the user glossary: its title and lines, fenced blocks included, outside code spans and link destinations, never use the whole words "engine" or "provider", in any case and with their plurals. Excluded sections are not checked; no allow list. The rule is stated in the project README's "Served documents" section. |
| H10 | No API shape or version change: document ids, section ids, term ids and code values are unchanged, and the help bundle is regenerated; only served text and the Beginner Guide's title change. The desktop application picks up the text when it next re-vendors; no desktop issue is filed. |
```

## Change log

None yet.
