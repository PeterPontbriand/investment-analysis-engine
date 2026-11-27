# Spec Issue 305: investor glossary wording

- **Owning plan:** [API plan](../API_CONTRACT_AND_SLICE_PLAN.md), sequence row `Issue 305` and decision record A.22, both
  written by step 1 of this spec.
- **Branch:** `docs/investor-glossary-wording`, from `main` at `ea0f03c` (`fix(ph): serve help headings as plain text
  (#309)`).
- **Decisions approved:** 2026-11-27, by the project owner (decisions G1 to G10 of the glossary-wording decision list).
- **Lane:** normal.

## Goal

The investor glossary speaks about markets, companies, data and methods, never about this project's machinery: no
"the engine", "Investment Analysis Engine", "provider" or "data provider" in any investor entry, a qualitative
explanation of the Nasdaq tiers, data-source status terms an investor can read, and a check that keeps it so.

## Decisions

Each line is recorded verbatim, with its approval date, in record A.22 by step 1.

- **G1** Recorded in the API plan as sequence row `Issue 305` and record A.22; this spec; branch
  `docs/investor-glossary-wording`; closes #305.
- **G2** Scope: every investor entry of `docs/user/GLOSSARY.md` (names, short definitions, bodies), with the page's
  title, introduction and group introductions, which are served with them. The command-line section and the
  contributor glossary change only to receive moved detail.
- **G3** "the engine" and "Investment Analysis Engine" become "this application" where the behavior matters to an
  investor and are removed where it does not; "a/the provider" and "data provider" become "a/the data source", or the
  source's name. Code values in backticks stay.
- **G4** Eight term names change, every id kept (table in step 2).
- **G5** The Nasdaq entry explains the three tiers qualitatively, with no numeric thresholds, and keeps one sentence
  naming the tier codes.
- **G6** Implementation detail with no investor relevance moves to the contributor glossary or is dropped; the moves
  are listed in step 2.
- **G7** `scripts/check_help_content.py` refuses the whole words "engine" and "provider" (any case, with their plurals)
  in an investor entry's name or text outside code spans and link destinations; no allow list.
- **G8** The served guides are not in this unit; issue #310 owns them and extends G7's check to them.
- **G9** Messages produced by code are not changed here; API.24 (#306, C27) owns them.
- **G10** No API shape or version change; term ids, anchors and code values stay; the help bundle is regenerated; no
  desktop issue.

## Out of scope

- The Beginner Guide, Finance Math and the strategy guides, including their links whose text names an old term name
  (issue #310).
- Any message produced by code, including the entry warnings' "No data provider recognizes" and "data providers could
  not be reached", the command line's "Data provider:" label and the settings messages' "The engine settings" (API.24,
  issue #306).
- The command-line section of the user glossary (below `<!-- help:exclude -->`): it is not edited.
- The contributor glossary's existing entries, including BaseDataClient's "Investment Analysis Engine supplements".
- Any term id, anchor, link destination, code value, schema, OpenAPI document, API version or `schema_version`.
- Any change to what an entry claims beyond the wording this spec gives; a sentence whose meaning seems wrong is
  reported, not fixed.
- The desktop repository.

## Allowed files

- `docs/project/milestones/v0.2/api/specs/issue-305.md` (this spec).
- `docs/project/milestones/v0.2/api/API_CONTRACT_AND_SLICE_PLAN.md`: §2's rows `Issue 305` and `API.24`, the new §3
  section, the new record A.22 in Appendix A.
- `docs/user/GLOSSARY.md`: lines above `<!-- help:exclude -->` only, exactly as step 2's table says.
- `docs/project/CONTRIBUTOR_GLOSSARY.md`: the one new entry of step 2 only.
- `docs/project/README.md`: the "Glossary entries" section, one new bullet (step 3).
- `scripts/check_help_content.py`
- `tests/scripts/test_check_help_content.py`
- `investment_analysis_engine/help/help_bundle.en.json` (regenerated only).
- Any other test file that fails only because it pins a glossary sentence or term name this spec changes: listed by
  name in the report. Any other failure is an escalation.

## Steps

1. **Spec and records.** Commit this spec as the branch's first commit. Then, in one commit, in the API plan:
   - §2: add row `| Issue 305 | [Investor glossary wording](#issue-305--investor-glossary-wording) | Next | |`
     directly above the `API.24` row, and change `API.24`'s status from `Next` to `Planned`.
   - §3, after the API.24 section, a new section:

     ```markdown
     ### Issue 305 — Investor glossary wording

     - **Problem:** investor glossary entries speak about this project's machinery ("the engine", "the provider"),
       the data-source status terms are named after it, and the Nasdaq entry explains how venue text is matched rather
       than what the tiers mean (engine issue 305).
     - **Decision:** investor entries use "this application" and "data source"; eight status term names change with
       their ids kept; the Nasdaq tiers are explained qualitatively; the help-content check refuses "engine" and
       "provider" in investor entries ([A.22](#a22-investor-glossary-wording-2026-11-27), G1 to G10).
     - **Scope:** the user glossary's investor section, one contributor glossary entry, the glossary rules in the
       project README, `scripts/check_help_content.py` and its tests, the regenerated help bundle.
     - **Branch:** `docs/investor-glossary-wording`.
     - **Detail:** this unit's spec: [specs/issue-305.md](specs/issue-305.md); decisions in
       [A.22](#a22-investor-glossary-wording-2026-11-27).
     ```

   - Appendix A, after A.21: the record under [Record to add](#record-to-add) below, verbatim.
   - Check: the documentation checks (`python scripts/check_doc_links.py`, `python scripts/check_sequence_tables.py`,
     `python scripts/check_package_dependencies.py`, `uv run ruff check .`, `uv run ruff format --check .`).
2. **Glossary rewrite (G2 to G6).** Line numbers are those of `docs/user/GLOSSARY.md` at `ea0f03c`. Apply each row:
   "Replace" swaps the quoted words where they occur on that line; "Becomes" replaces the whole line. Every other word
   of the line, every `<a id=...></a>` line and every link destination stays as it is. Lines not listed do not change.

   | Line | Entry or place | Change |
   | :--- | :--- | :--- |
   | 1 | Page title | Becomes `# Glossary` |
   | 3 | Introduction | Replace "used in Investment Analysis Engine." with "used in this application." |
   | 37 | Applicability Status | Replace "Investment Analysis Engine uses machine-readable statuses including" with "Results carry machine-readable statuses, including" |
   | 47 | Analysis Warning | Replace "instead of provider data" with "instead of a data source's value" |
   | 81 | Analysis Run | Replace "a data provider" with "a data source" |
   | 134 | Data Provider | Becomes `### Data Source` |
   | 139 | SEC | Replace "The engine uses its public data as a source of company financial facts." with "Its public data is a source of company financial facts for the analyses." |
   | 159 | Cache | Replace "Otherwise the engine asks an allowed provider or reports the input unavailable." with "Otherwise the value is fetched from an allowed data source, or the input is reported unavailable." |
   | 175 | Current Quote / Current Market Price | Replace "the provider can" with "the data source can" |
   | 177 | Current Quote / Current Market Price | Replace "the selected provider" with "the selected data source", and "A current-only quote adapter therefore returns unavailable for historical financial-fact requests rather than substituting today's price." with "A source that gives only current quotes therefore gives no quote for a historical as-of date, and today's price is never substituted." |
   | 179 | Current Quote / Current Market Price | Replace "when the provider response was obtained" with "when the data source's answer was obtained", and "The current Yahoo adapter retains retrieval time and explicitly reports unknown market observation time." with "Quotes from Yahoo Finance keep their retrieval time and report the market observation time as unknown." |
   | 197 | Instrument Profile | Replace "The engine keeps" with "This application keeps", and "without contacting a provider" with "without contacting a data source" |
   | 213 | Provenance | Replace "source kind, provider, source field" with "source kind, data source, source field" |
   | 249 | Override | Replace "from the cache or a provider" with "from the cache or a data source" |
   | 253 | Resolution Precedence | Replace "a configured provider" with "a configured data source" |
   | 261 | Input Source | Replace "from a data provider, or the engine derived it from other inputs." with "from a data source, or it was derived from other inputs." |
   | 281 | Capital Expenditure Sign | Replace "How a data provider writes" with "How a data source writes" |
   | 283 | Capital Expenditure Sign | Replace "The engine records the convention" with "The convention is recorded", and "whichever sign the provider used" with "whichever sign the data source used" |
   | 313 | Listing Venue | Replace "as the data provider reports it" with "as the data source reports it" |
   | 315 | Listing Venue | Becomes: `You see the data source's own wording and, when this application recognizes that wording, the name of the market it stands for. A venue it does not recognize is shown in the data source's words alone, and this entry explains it. The venue is as the data source reports it, and two data sources can report different venues for the same ticker. A cryptocurrency is not listed on an exchange, and a data source's venue text for one may name where its price comes from rather than an exchange. See [instrument profile](#instrument-profile) and [security identity](#security-identity).` |
   | 317 | Listing Venue | Replace "The markets the engine recognizes" with "The markets this application recognizes" |
   | 323 | Nasdaq Stock Market (G5) | Becomes: `Nasdaq lists companies in three tiers: the Global Select Market, the Global Market and the Capital Market. Its listing standards (size, financial and liquidity requirements) are strictest for the Global Select Market, and the Capital Market serves smaller companies. A company's tier is a rough sign of its size and trading liquidity, not a rating. Data sources write the tiers as NasdaqGS, NasdaqGM and NasdaqCM. See [listing venue](#listing-venue).` |
   | 335 | NYSE Group Exchange | Replace "The source does not say which of them the security is listed on, so the engine does not either." with "The data source does not say which of them the security is listed on, so only the group is shown." |
   | 353 | Cboe U.S. Equities Exchange | Same replacement as line 335 |
   | 413 | Quote Currency | Replace "as the data provider reports it" with "as the data source reports it" |
   | 415 | Quote Currency | Replace "A provider may report" with "A data source may report" |
   | 443 | Three-Year-Average EPS | Becomes: `It is the standard Graham Number earnings basis, and the Graham Growth Value strategy's basis when it uses SEC EDGAR earnings data, reflecting Graham's defensive-investor emphasis on average earnings over the preceding three years.` |
   | 461 | Anchor Filing | Replace "The engine reads the annual reports filed by the as-of date from the newest." with "The analysis reads the annual reports filed by the as-of date, starting from the newest.", and "The engine never warns early." with "No warning is given early." |
   | 479 | Split-Adjusted Close | Replace "in the provider's split history" with "in the data source's split history" |
   | 513 | BVPS (Book Value Per Share) | Becomes: `When it comes from SEC EDGAR data, it is derived from eligible fiscal-year-end balance-sheet components rather than read from a single reported figure.` |
   | 557 | Capital Expenditures (CapEx) | Becomes: `Data sources write CapEx with different signs, so it is converted to a positive amount of spending and the conversion is kept in provenance.` |
   | 559 | Capital Expenditures (CapEx) | Replace "From SEC filings the engine uses" with "From SEC filings the analysis uses" |
   | 567 | Free Cash Flow (FCF) | Replace "another provider may use" with "another data source may use" |
   | 583 | Split-Adjustment Window | Replace "Where a data provider's adjustment" with "Where a data source's adjustment", and "the date the provider adjusted to" with "the date the data source adjusted to" |
   | 585 | Split-Adjustment Window | Replace "the provider's adjustment" with "the data source's adjustment" |
   | 595 | Valuation | Replace "In Investment Analysis Engine a valuation result" with "Here a valuation result" |
   | 603 | Intrinsic Value | Replace "Investment Analysis Engine avoids using this term without qualification for the Graham Number." with "The Graham Number is never called an intrinsic value without qualification." |
   | 733 | Price Basis | Replace "Providers revise adjusted prices" with "Data sources revise adjusted prices" |
   | 841 | Growth-Estimation Policy | Becomes: `A language model, a data source or a silent default never invents growth.` |
   | 847 | AAA Corporate Bond Yield (G6) | Becomes: `No live series is connected yet, so the strategy takes a yield you supply.` The removed sentence moves to the contributor entry below |
   | 859 | Current AAA Yield (G6) | Becomes: `It is a value you supply and is identified as such.` The removed clause moves to the contributor entry below |
   | 1004 | FCF Growth Indeterminate | Replace "the engine cannot make the classification from the evidence it may use." with "the classification cannot be made from the evidence the analysis may use." |
   | 1040 | Unavailable Forward Evidence | Replace "The engine has no approved source of consensus estimates yet" with "No source of consensus estimates is approved yet" |
   | 1094 | Insufficient Growth Evidence | Replace "the engine cannot say" with "the analysis cannot say" |
   | 1185 | Group introduction | Replace "a provider failure" with "a data source failure" |
   | 1198 | Unavailable | Replace "whose data provider answered" with "whose data source answered" |
   | 1202 | Failed | Replace "or a data provider failed" with "or a data source failed" |
   | 1204 | Failed | Replace "[provider error](" with "[data source error](", "A provider that answered with nothing" with "A data source that answered with nothing", and "[provider returned no data](" with "[no data from the data source](" |
   | 1222 | Input Unavailable | Replace "a provider that answered with nothing" with "a data source that answered with nothing" |
   | 1226 | Invalid Input | Replace "or read from provider data" with "or read from a data source" |
   | 1228 | Invalid Input | Replace "the inputs or the provider data were invalid; the details are kept in the engine's log." with "the inputs or the data source's data were invalid; the details are kept in this application's log." |
   | 1231 | Provider Error (G4) | Becomes `### Data Source Error` |
   | 1232 | Data Source Error | Replace "A data provider failed" with "A data source failed" |
   | 1234 | Data Source Error | Replace "The failure code of the same name is used when the provider's failure" with "The failure code `provider_error` is used when the data source's failure", and "A provider that answered with nothing is not a provider error;" with "A data source that answered with nothing is not a data source error;" |
   | 1237 | Provider Unreachable (G4) | Becomes `### Data Source Unreachable` |
   | 1238 | Data Source Unreachable | Replace "The data provider" with "The data source" |
   | 1243 | Provider Rate-Limited (G4) | Becomes `### Data Source Limiting Requests` |
   | 1244 | Data Source Limiting Requests | Replace "The data provider" with "The data source" |
   | 1249 | Provider Unexpected Response (G4) | Becomes `### Unexpected Answer from a Data Source` |
   | 1250 | Unexpected Answer from a Data Source | Replace "The data provider answered" with "The data source answered", and "a form the engine reads" with "a form this application reads" |
   | 1252 | Unexpected Answer from a Data Source | Replace "The provider may have changed" with "The data source may have changed" |
   | 1255 | Provider Returned No Data (G4) | Becomes `### No Data from the Data Source` |
   | 1256 | No Data from the Data Source | Replace "The data provider answered" with "The data source answered" |
   | 1258 | No Data from the Data Source | Replace "Unlike an unreachable provider, the provider worked;" with "Unlike an unreachable data source, the data source worked;", "and the provider check still runs, so a mistyped ticker can be told from a provider that is down." with "and the data source is still checked, so a mistyped ticker can be told from a data source that is down." |
   | 1261 | Provider Healthy (G4) | Becomes `### Data Source Answering Normally` |
   | 1262 | Data Source Answering Normally | Replace "to the data provider" with "to the data source" |
   | 1264 | Data Source Answering Normally | Becomes: `The check is made after a failure to tell a problem with the data source from a problem with one ticker. See [data source](#data-provider).` |
   | 1267 | Provider Not Checked (G4) | Becomes `### Data Source Not Checked` |
   | 1268 | Data Source Not Checked | Replace "to the data provider" with "to the data source" |
   | 1270 | Data Source Not Checked | Replace "A provider is checked" with "A data source is checked" |
   | 1274 | Unexpected Failure | Becomes: `The analysis failed in a way this application did not anticipate. The details are in this application's log, not in the message shown.` |
   | 1280 | Historical Data Quality Failure | Replace "failed the engine's data-quality checks" with "failed the data-quality checks" |
   | 1282 | Historical Data Quality Failure | Replace "It is not a provider outage: the provider answered," with "It is not a data source outage: the data source answered," |
   | 1292 | Configuration Error | Replace "A setting of the engine prevents" with "A setting of this application prevents" |
   | 1294 | Configuration Error | Becomes: `The message is written for the person who set up this application.` |
   | 1309 | Database Failure | Replace "this version of the engine" with "this version of the application" |
   | 1311 | Database Failure | Replace "the engine may not use" with "this application may not use" |
   | 1314 | Database Failure | Replace "the engine's own migration resources are missing or inconsistent" with "the files this application uses to set up or upgrade a database are missing or inconsistent" |
   | 1320 | Stored Data Unreadable | Replace "this version of the engine" with "this version of the application" |
   | 1326 | Unsupported Run Version | Replace "this version of the engine reads" with "this version of the application reads" |
   | 1340 | Instrument Profile Not Found | Replace "an earlier version of the engine" with "an earlier version of the application" |
   | 1344 | Ticker Not Recognized | Replace "the data providers answered" with "the data sources answered" |
   | 1346 | Ticker Not Recognized | Replace "A provider sometimes answers" with "A data source sometimes answers", and "[provider returned no data](" with "[no data from the data source](" |
   | 1350 | Ticker Not Checked | Replace "because a data provider or the engine's database" with "because a data source or this application's database" |
   | 1352 | Ticker Not Checked | Replace "asks the data providers" with "asks the data sources", "After the providers could not be reached, asked the engine to wait," with "After the data sources could not be reached, asked this application to wait,", "[provider unreachable](" with "[data source unreachable](", and "[provider rate-limited](" with "[data source limiting requests](" |
   | 1394 | Error Category | Replace "A failure the engine cannot place is treated as this category." with "A failure that fits neither category is treated as this one." |
   | 1412 | Incompatible Inputs | Replace "The engine does not convert or substitute to make the inputs fit." with "Nothing is converted or substituted to make the inputs fit." |
   | 1416 | Ambiguous Fact | Replace "so the engine chooses none of them" with "so none of them is used" |
   | 1424 | Not Available As Of | Replace "The engine never uses information from after the boundary." with "No information from after the boundary is used." |
   | 1438 | Override Only | Replace "from a data provider" with "from a data source" |
   | 1450 | Earlier Basis | Replace "so the engine never combines them" with "so the analysis never combines them" |

   Then, in `docs/project/CONTRIBUTOR_GLOSSARY.md`, under "Market data architecture", directly after the
   BaseDataClient entry, add this entry (G6 destination for lines 847 and 859):

   ```markdown
   <a id="provider"></a>
   ### Provider
   The code that fetches data from one data source, such as SEC EDGAR or Yahoo Finance, behind a data contract. Investor text says data source instead.

   A provider that supplies an economic series, such as a future AAA corporate bond yield, keeps in provenance the exact series, its units, its observation and publication dates, and its rating and maturity scope.
   ```

   Check: `python scripts/check_help_content.py`, then the documentation checks. A row whose quoted text is not found
   on its line is an escalation, never a guess.
3. **The check (G7).** In `scripts/check_help_content.py`:
   - A constant `INVESTOR_FORBIDDEN_WORDS_RE = re.compile(r"\b(?:engine|provider)s?\b", re.IGNORECASE)`.
   - `Entry` gains `text: str`: the entry's body, from the line after the heading (after the exclude marker when there
     is one) to the next heading, without fenced blocks, id lines (`ANCHOR_ID_RE`), code spans and link destinations
     (the link text stays), lines joined by single spaces. `parse_glossary` fills it.
   - `check_glossary` gives, for each investor entry of the user glossary (the same condition as `_link_problems`),
     one problem per distinct forbidden word found in the name, reason
     `the name uses the internal word '<word as written, lowercased>'`, and one per distinct word found in the text,
     reason `the text uses the internal word '<word>'`; a reason ends with
     `; see docs/project/README.md, Glossary entries`.
   - The module docstring's list of what the checker requires gains this rule, in one sentence.
   - In `docs/project/README.md`, section "Glossary entries", after the "Short definition" bullet, add:
     "- **Investor wording:** an investor entry speaks about markets, companies, data and methods, not about this
     software. Its name and text, outside code spans and link destinations, never use the words engine or provider:
     write this application where its behavior matters to an investor, and data source, or the source's name, for
     where data comes from."
   - Tests in `tests/scripts/test_check_help_content.py`, a new class `TestInvestorWording`, using the file's existing
     helpers: a name "Provider Healthy" fails; text "the engine reads it" fails; "Engines" and "PROVIDERS" fail; a
     code span `` `provider_error` `` passes; a link `[unreachable](#provider-unreachable)` passes; a link text
     `[provider error](#status-provider-error)` fails; the next entry's id line `<a id="provider-no-data"></a>` inside
     a body passes; an entry in an excluded section with "engine" passes; the contributor glossary with "provider"
     passes; "providential" and "engineering" pass (whole words only).
   - Check: slice check.
4. **Help bundle (G10).** Run `uv run python -m scripts.generate_help`. The bundle's term ids (`terms` keys) and group
   and document ids must be unchanged; only names and text change. Check: slice check.
5. **Close the row.** In the API plan §2, set `Issue 305`'s status to `Complete` with today's date in Completed, and
   set `API.24` to `Next` (AGENTS.md §12). Check: the documentation checks.
6. **Finish.** Run the slice check once, commit with the PR text's title, push the branch
   (`git push -u origin docs/investor-glossary-wording`) and report. Do not open the pull request until the spec
   author's review is clean; then open it with the PR text below and assign it to the project owner.

## Norms and safeguards

- The [escalation table in AGENTS.md §11](../../../../../../AGENTS.md#escalation-in-a-spec-driven-unit) applies.
- No attribution of any kind (AGENTS.md §3), no new dependency, no change to `pyproject.toml` or `uv.lock`.
- Ids, anchors, link destinations and code values never change; a renamed heading keeps the `<a id>` line above it.
- The short-definition rules still hold for every changed first paragraph (200 characters, two sentences, plain text).
- A sentence in step 2's table that would change what an entry claims, or a word the table misses that the new check
  finds, is an escalation to the spec author; never settled in the glossary.
- Issue #116 evidence: stop and keep the run directory (AGENTS.md §10).

## Acceptance checks

1. Slice check passes: the wrapper's closing summary shows every step passed.
2. No investor entry uses the words:
   `python scripts/check_help_content.py` exits 0, and `uv run pytest tests/scripts/test_check_help_content.py -q`
   passes, including `TestInvestorWording`.
3. Ids unchanged: `git --no-pager diff origin/main...HEAD -- docs/user/GLOSSARY.md | grep -E '^[-+]<a id'` prints
   nothing.
4. Bundle ids unchanged:
   `uv run python -c "import json,subprocess;old=json.loads(subprocess.run(['git','show','origin/main:investment_analysis_engine/help/help_bundle.en.json'],capture_output=True,text=True,check=True).stdout);new=json.load(open('investment_analysis_engine/help/help_bundle.en.json',encoding='utf-8'));print(sorted(old['terms'])==sorted(new['terms']))"`
   prints `True`.
5. The renamed names are served:
   `uv run python -c "import json;t=json.load(open('investment_analysis_engine/help/help_bundle.en.json',encoding='utf-8'))['terms'];print(t['provider-no-data']['name'], '|', t['data-provider']['name'])"`
   prints `No Data from the Data Source | Data Source` (if the term's name key is not `name`, use the bundle's key and
   say so in the report).
6. `uv run python -m scripts.generate_help --check` passes.
7. `git --no-pager diff --stat origin/main...HEAD` lists only allowed files.

## Report

The final commit hash; the diff stat; the last slice-check result with its `gate-output.txt` path; the result of each
acceptance check; any test file changed under the last allowed-files line, with why; every escalation with the
table row that triggered it; and "Pilot measures: escalations N, of which spec defects N; owner actions N".

## PR text

Title: `docs(ph): investor glossary in investor words (issue 305)`

```markdown
## Summary

The investor glossary now speaks about markets, companies, data and methods instead of this project's machinery.

## User-visible changes

- Glossary entries say "this application" and "data source" instead of "the engine" and "provider".
- Eight term names change, with their ids unchanged: Data Source, Data Source Error, Data Source Unreachable, Data
  Source Limiting Requests, Unexpected Answer from a Data Source, No Data from the Data Source, Data Source Answering
  Normally and Data Source Not Checked.
- The Nasdaq Stock Market entry explains what the three Nasdaq tiers mean for an investor.
- The help bundle is regenerated. No API shape, term id, code value or version changes.

## For contributors

- `scripts/check_help_content.py` refuses the words "engine" and "provider" in an investor entry outside code spans
  and link destinations; the rule is in `docs/project/README.md`, "Glossary entries".
- The contributor glossary gains Provider, which holds the AAA-yield provenance requirement moved out of the investor
  entries.

## Records

- API plan: row Issue 305 and record A.22. The served guides follow in #310; messages produced by code are reworded
  by API.24 (#306).

Closes #305
```

## Record to add

Step 1 appends this record to the API plan's Appendix A, after A.21, exactly as written here.

```markdown
### A.22 Investor glossary wording (2026-11-27)

Approved by the project owner on 2026-11-27, as decisions G1 to G10. Closes engine issue 305; the served guides follow
in engine issue 310.

| # | Decision |
| :--- | :--- |
| G1 | Recorded in this plan as sequence row Issue 305 and this record; the unit's spec is `specs/issue-305.md`, its branch `docs/investor-glossary-wording`. This plan owns it because the help bundle and the glossary rules came from API.5 and API.6. |
| G2 | Scope: every investor entry of the user glossary (names, short definitions and bodies), with the page's title, introduction and group introductions, which are served with them. The command-line section and the contributor glossary change only to receive moved detail. |
| G3 | "the engine" and "Investment Analysis Engine" become "this application" where the behavior matters to an investor, and are removed where it does not. "a/the provider" and "data provider" become "a/the data source", or the source's name (SEC EDGAR, Yahoo Finance) where one is meant. Code values in backticks, such as `provider_no_data`, stay, since they are API values. "This application" reads correctly in the desktop application and on the command line. |
| G4 | Term names change, with every id and anchor kept: Data Provider becomes Data Source; Provider Error, Data Source Error; Provider Unreachable, Data Source Unreachable; Provider Rate-Limited, Data Source Limiting Requests; Provider Unexpected Response, Unexpected Answer from a Data Source; Provider Returned No Data, No Data from the Data Source; Provider Healthy, Data Source Answering Normally; Provider Not Checked, Data Source Not Checked. |
| G5 | The Nasdaq entry explains the three tiers, Global Select Market, Global Market and Capital Market: listing standards (size, financial and liquidity requirements) are strictest for Global Select and the Capital Market serves smaller companies; a company's tier is a rough sign of its size and trading liquidity, not a rating. The tier codes stay in one sentence, because an investor sees them beside the name. No numeric thresholds: they change over time and would need checking against Nasdaq's rules on every edit. |
| G6 | Detail with no investor relevance moves to the contributor glossary, or is dropped where a contributor document already says it. The unit's spec lists each move. |
| G7 | `scripts/check_help_content.py` refuses the whole words "engine" and "provider", in any case and with their plurals, in an investor entry's name or text outside code spans and link destinations. It runs in the gate and in the help-bundle generator, like the other glossary rules. No word-level allow list. |
| G8 | The served guides (Beginner Guide, Finance Math's served sections, the strategy guides) are not in this unit. Engine issue 310 rewords them and extends G7's check to served sections; it is placed right after this unit. |
| G9 | Messages produced by code that say "the engine's database" or "data provider" are not changed here; API.24 rewords investor messages ([A.21](#a21-explain-why-a-result-has-no-number-2026-11-25), C27). |
| G10 | No API shape or version change: term ids, anchors and code values stay, only the served names and text change, and the help bundle is regenerated. Help text carries no compatibility guarantee; ids do. The desktop application picks up the text when it next re-vendors; no desktop issue is filed. |
```

## Change log

None yet.
