# Spec API.23: SEC EDGAR ticker coverage, explained and warned

- **Owning plan:** [API plan](../API_CONTRACT_AND_SLICE_PLAN.md), slice API.23 and decision record A.20, both written by
  step 1 of this spec.
- **Branch:** `feat/api-sec-coverage`, from `main` at `8b72e8ecfa655ebf220e3e4ae60edf1845dc230f`.
- **Decisions approved:** 2026-11-25, by the project owner (decisions C1 to C31 of the Canadian-tickers decision list;
  this unit implements C1 to C11 and records C12 to C22 and C23 to C31 as planned work).
- **Lane:** normal.

## Goal

When a ticker is not in SEC EDGAR's ticker list (for example `NTR.TO`, Nutrien on the Toronto Stock Exchange), an
investor learns why the strategies that read SEC filings are unavailable for it: from the run's reason, from a warning
when the ticker is added to a watchlist, from the glossary, and from a named Canadian listing venue instead of the bare
word "Toronto". The project plans record the Canadian-listings work package and the order of the engine work that
follows.

## Decisions

Each line is recorded verbatim, with its approval date, in record A.20 by step 1.

- **C1** New investor glossary entry "SEC EDGAR Ticker List" (`sec-ticker-list`), linked from EDGAR, Provider Returned
  No Data, each strategy entry whose strategy reads SEC filings, the new warning's entry and each Canadian venue entry.
- **C2** The reason of a run stopped because SEC's ticker list does not include the ticker reads "SEC EDGAR's ticker
  list does not include {ticker}, so {input} could not be read from SEC filings. SEC EDGAR lists companies under their
  US ticker symbols only.", `{input}` being the label of the required input that needed the company identifier. Amends
  the message of A.16's E7 and E13 for this case only.
- **C3** New runs get the new message; stored runs keep theirs. No method, result-schema, evidence-codec or document
  version changes.
- **C4** Each strategy declares a selection-aware predicate, in its `StrategyBehavior`, saying whether a selection
  reads SEC EDGAR.
- **C5** New entry warning code `ticker_not_in_sec_list`, an addition to the open warning-code vocabulary in `/v1`
  ([S4](../API_2_SLICE_PLAN.md#s4-the-v1-additions-rule-2026-11-03)), with its own glossary entry
  `entry-warning-ticker-not-in-sec-list`. Given at most once per ticker, `reason_code` null, never refusing an entry.
- **C6** Its message: "{ticker} is not in SEC EDGAR's ticker list, so {strategies} will be unavailable for it: they
  read the company's financial statements from SEC filings. SEC EDGAR lists a company only under its US ticker symbol,
  so a ticker on an exchange outside the United States is not in the list even when the company files with the SEC."
- **C7** With no SEC identity set up, no new warning.
- **C8** No warning before a direct analysis; its result carries C2's reason.
- **C9** Canadian listing-venue codes `tsx`, `tsxv`, `cboe_canada` and `cse`, each mapped only from Yahoo values
  captured live in this unit and recorded in the mapping record, each with an investor glossary entry linking
  `sec-ticker-list`.
- **C10** The command line prints the new warning as it prints the existing ones (A.14 P9).
- **C11** No desktop change in this unit.
- **C12 to C22, C23 to C31** Recorded as planned work by step 1 only: work package CAN, API.24, and the engine order.

## Out of scope

- Linking a Canadian ticker to its SEC filer, currency conversion, and any IFRS change (#293, #294): work package CAN.
- Explanations of other no-answer results, and rewording other reason messages (API.24, issue #306).
- Rewording existing glossary entries beyond the links C1 adds, including the SEC entry's "The engine uses its public
  data" (#305).
- The help section heading with Markdown (#304).
- Preferred-share evidence for book value (issue #307).
- Any change to the CIK override file's behavior, to the instrument profile lookup's provider order or caching, or to
  what a refresh or `/v1/analyses` checks.
- The desktop repository.

## Allowed files

Plans and records:

- `docs/project/milestones/v0.2/api/API_CONTRACT_AND_SLICE_PLAN.md`: §2 sequence rows, new sections API.23 and API.24
  in §3, new records A.20 and A.21 in Appendix A.
- `docs/project/milestones/v0.2/api/API_22_LISTING_VENUE_MAPPING_RECORD.md`: §1, §3, §3.1 and §5.
- `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`: the `CAN` code bullet and the sequence row only.
- `docs/project/milestones/v0.2/step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md`: §2's prose under the table only.
- `docs/project/milestones/v0.2/api/specs/api-23.md` (this spec).

Code:

- `investment_analysis_engine/reporting/provider_messages.py`
- `investment_analysis_engine/core/entry_warnings.py`
- `investment_analysis_engine/application/entry_check.py`
- `investment_analysis_engine/data/sec_edgar/financial_facts.py`: one new public method (step 4) and its docstring
  only.
- `investment_analysis_engine/data/listing_venue.py`
- `investment_analysis_engine/strategy_wiring.py`
- `investment_analysis_engine/strategies/<each strategy>/selection.py`: one new predicate function each.
- `investment_analysis_engine/workspace_documents/watchlist.py`: descriptions of the warning fields only, if they name
  the closed set of codes.
- `investment_analysis_engine/help/help_bundle.en.json` (regenerated only).
- `schemas/*.json` (regenerated only).
- `scripts/new_strategy.py`, `scripts/strategy_templates/selection.py.tmpl`, `scripts/strategy_sites.toml`,
  `scripts/strategy_conformance.py`: only what the generator and the conformance check need for the new behavior field.
- `tests/specimen/**`: only what the new behavior field needs.

User documents:

- `docs/user/GLOSSARY.md`: the new entries and the added links only.
- `docs/user/API.md`, `docs/user/USAGE.md`, `docs/user/WORKSPACE.md`, `docs/user/FINANCE_MATH.md`: the places that quote
  the old reason message or list the warning codes.
- `docs/project/STRATEGY_DEVELOPMENT.md`: the behavior-bundle description, for the new field only.

Tests:

- `tests/application/test_entry_check.py`, `tests/api/test_entry_warnings.py`,
  `tests/workspace_documents/test_entries_added_document.py`, `tests/core/test_provider_stopped_status.py`,
  `tests/test_unknown_ticker_unavailable.py`, `tests/data/test_listing_venue.py`, `tests/reporting/test_provider_messages.py`
  (new if absent), and a new `tests/test_reads_sec_edgar.py`.
- `tests/scripts/test_new_strategy.py` and `tests/scripts/test_new_strategy_end_to_end.py`: only the `selection` stub expectations for `reads_sec_edgar`; new `tests/scripts/generator_fills/selection.py.fill`.
- Any other test file that fails only because it pins the old reason text or the closed list of venue codes or warning
  codes: listed by name in the report.

## Steps

1. **Spec and records.** Commit this spec as the branch's first commit. Then, in one commit:
   - API plan §2: add row `API.23` (scope "SEC EDGAR ticker coverage, explained and warned", link to its section)
     with status `Next`, above API.20; add row `API.24` ("Explain why a result has no number") `Planned`, above
     API.20. Keep the table's status order.
   - API plan §3: section **API.23** with Problem (issue #302), Decision (C1 to C11, link to A.20), Scope (this spec's
     allowed files, summarized), Branch `feat/api-sec-coverage`, Detail "this slice's spec:
     `[specs/api-23.md](specs/api-23.md)`; decisions in A.20". Section **API.24** with Problem (issue #306), Decision
     (C23 to C30, link to A.21), Scope "every strategy's documents and text, the glossary, tests", Branch
     `feat/api-no-answer-explanations`, Detail `⚠ no slice plan yet`.
   - API plan Appendix A, after A.19: the two records under [Records to add](#records-to-add) below, verbatim.
   - v0.2 implementation plan: a `CAN` bullet in the codes list: "`CAN` — short for "Canadian listings" (umbrella
     `[issue #301](https://github.com/PeterPontbriand/investment-analysis-engine/issues/301)`): makes the strategies that
     read company financial facts usable for tickers listed in Canada. CAN.0 gathers evidence and writes the plan;
     CAN.1 links a Canadian ticker to its SEC filer and folds in #293; CAN.2 converts currencies for price comparisons;
     CAN.3, only if approved later, adds a source for companies that do not file with the SEC. Its row is numbered
     `15B`. Approved by the project owner on 2026-11-25 (decisions C12 to C22, `[API plan A.20](api/API_CONTRACT_AND_SLICE_PLAN.md#a20-sec-edgar-ticker-coverage-explained-and-warned-2026-11-25)`).
     Engine order from that date: API.23, #304, #305, API.24, CAN.0, CAN.1, #307, API.20 and API.21, CAN.2, then
     Step 3.5's 3.5.5." Add row `15B | Canadian listings (CAN) | Planned |` linking to issue #301, placed by the
     sequence-table rules.
   - Step 3.5 §2 prose: one line: "3.5.5 waits for the engine order recorded in the implementation plan's `CAN` entry
     (2026-11-25)."
   - Check: the documentation checks (`python scripts/check_doc_links.py`, `python scripts/check_sequence_tables.py`,
     `python scripts/check_package_dependencies.py`, both Ruff checks).
2. **Run reason (C2, C3).** In `reporting/provider_messages.py`, a `ticker_unlisted` failure whose `provider_id` is SEC
   EDGAR's returns C2's text with `{input}` = the `what` the caller passes. A `ticker_unlisted` failure of any other
   provider keeps today's text. When `what` is empty, `{input}` is "the company's financial statements" (a call site whose failure record names no input, such as FCF Growth's scope failure, must never print a blank). Update the module and function docstrings. Update the tests that pin the old text, and
   add one test per caller path (Graham via `_graham/outcome.py`, Piotroski, FCF Growth's two call sites) proving the
   message names the input. Update `docs/user/FINANCE_MATH.md` §"provider no data" paragraph and `docs/user/USAGE.md`'s
   quotation. Check: slice check.
3. **Strategy predicate (C4).** Add `reads_sec_edgar: Callable[[SelT], bool]` to `StrategyBehavior`, a guarded
   `reads_sec_edgar_for(selection: object) -> bool` to `BehaviorView` (exact-type check as its siblings), and in
   `strategy_wiring.py` one public function `sec_edgar_strategy_label(selection: SelectionMember) -> str | None`
   returning the descriptor's `label` when the selection reads SEC EDGAR, else `None` (`UndeclaredStrategyError` for an
   undeclared selection). Each strategy defines `reads_sec_edgar(selection) -> bool` in its `selection.py`:
   - Momentum: always `False`.
   - Graham Number: `False` exactly when both `eps_override` and `bvps_override` are set; else `True`.
   - Graham Growth: `False` exactly when `eps_override` is set; else `True`.
   - FCF Growth and Piotroski: always `True`.
   `tests/test_reads_sec_edgar.py` runs, for each strategy and each case above, a run through the strategy's analyzer
   with a stubbed SEC adapter whose ticker list lacks the ticker and a Yahoo stub that answers, and asserts that a
   selection the predicate says reads SEC EDGAR stops with `provider_no_data` and the C2 reason, and one it says does
   not is not stopped by the unlisted ticker. If a case behaves otherwise, stop and escalate (row: spec contradicts the
   code). Update the generator so a new strategy's `selection.py` gets `reads_sec_edgar` (an `unfilled_stub` body is
   allowed there by AGENTS.md §3) and its behavior bundle passes it; update the conformance site list only if its check
   requires it; update the specimen and `STRATEGY_DEVELOPMENT.md`'s behavior-bundle description. Check: slice check.
4. **SEC list membership.** Add one public method to the SEC financial-facts adapter,
   `lists_ticker(ticker: str) -> bool`: `True` when the ticker has a CIK override or SEC's ticker file lists it (under
   one CIK or several); `False` only when the file was loaded and does not list it and there is no override. It uses
   `_load_ticker_metadata` and the same tables `_resolve_cik` reads, and raises what loading raises. Unit-test the four
   cases with a stubbed file. Check: slice check.
5. **Entry warning (C5, C6, C7, C10).** In `core/entry_warnings.py`: add `TICKER_NOT_IN_SEC_LIST =
   "ticker_not_in_sec_list"` with its docstring, its term `entry-warning-ticker-not-in-sec-list` in
   `ENTRY_WARNING_CODE_TERMS`, C6's template with arguments `ticker` and `strategies`, and
   `not_in_sec_list_warning(ticker, strategy_labels)` which joins labels in order of first appearance as "A", "A and B",
   "A, B and C". In `application/entry_check.py`: `check_tickers` takes the entries (ticker and selection) instead of
   tickers. For each distinct ticker that the lookup identified (no other warning), when an SEC provider was built
   (`build_sec_production_provider` succeeds, once per check) and at least one of that ticker's new entries reads SEC
   EDGAR, ask `lists_ticker`; `False` gives the warning with the labels of those entries' strategies, each once, in
   order of first appearance. A failure while asking (a `DataFetchError`, `FinancialProviderError` or database error)
   gives no warning for that ticker, is logged with its traceback through operational logging, and does not stop the
   check. Today's rules for `ticker_not_recognized` and `ticker_not_checked`, including the stop rule, are unchanged.
   Update the field descriptions in `workspace_documents/watchlist.py` if they list the codes; regenerate the schemas
   and `schemas/openapi.json`; `EntriesAddedDocument.schema_version` stays 1 (S4). Tests: warning given (one and
   several strategies), not given for Momentum-only entries, for fully overridden Graham entries, for a listed ticker,
   for an overridden ticker, without an SEC identity, after a `lists_ticker` failure; the CLI prints it under
   `Warnings:`; the API returns it with `template`, `arguments` and `message` consistent. Check: slice check.
6. **Venue codes (C9).** On the owner's machine, capture live, read-only, through the installed `yfinance`
   `Ticker.info`, the `fullExchangeName` and `exchange` of at least two tickers per venue: Toronto Stock Exchange
   (`NTR.TO`, `SHOP.TO`), TSX Venture Exchange (two `.V` tickers), Cboe Canada (two `.NE` tickers) and Canadian
   Securities Exchange (two `.CN` tickers). Check each market identifier code (`XTSE`, `XTSX`, `NEOE`, `XCNQ`) against
   the ISO 10383 list at `https://www.iso20022.org/sites/default/files/ISO10383_MIC/ISO10383_MIC.csv`, as the mapping
   record §5 did. Add the codes `TSX = "tsx"`, `TSXV = "tsxv"`, `CBOE_CANADA = "cboe_canada"`, `CSE = "cse"` to
   `ListingVenue`, each captured value to `YAHOO_VENUES` with a comment naming its field, the four terms to
   `LISTING_VENUE_TERMS`, and record every capture (date, ticker, both values) and the MIC check in the mapping record
   §1, §3, §3.1 (remove `Toronto` from the unmapped list) and §5. A venue whose values could not be captured, or a MIC
   the list does not confirm, is left out and named in the report; it is not guessed. No other venue table changes.
   Tests in `tests/data/test_listing_venue.py`. Check: slice check.
7. **Glossary (C1, C5, C9).** Add to `docs/user/GLOSSARY.md`, each with its id line, Title Case heading, a short
   definition that meets the rules in `docs/project/README.md` "Glossary entries", and the body below (body wording may
   be adjusted only to meet those rules; any other change is an escalation):
   - `sec-ticker-list`, **SEC EDGAR Ticker List**, in "Market data and timing" after EDGAR. Definition: "The SEC's list
     of the companies that file with it, each under its US ticker symbol." Body: "A company listed on an exchange
     outside the United States appears only under its US symbol, if it has one. Nutrien is NTR on the New York Stock
     Exchange, and NTR.TO on the Toronto Stock Exchange is not in the list. A company that does not file with the SEC is
     not in it at all. An analysis that reads a company's financial statements from SEC filings finds the company
     through this list, so it is unavailable for a ticker the list does not include. See `[EDGAR](#edgar)` and
     `[listing venue](#listing-venue)`."
   - `entry-warning-ticker-not-in-sec-list`, **Ticker Not in SEC EDGAR's List**, beside the two existing entry
     warnings. Definition: "When an entry was added, the ticker was recognized but is not in SEC EDGAR's ticker list.
     The entry was still added." Body: "The strategies of the new entries that read financial statements from SEC
     filings will be unavailable for this ticker. Strategies that use only prices still work. A company listed outside
     the United States may file with the SEC under its US ticker symbol; see `[SEC EDGAR ticker list](#sec-ticker-list)`."
   - `listing-venue-tsx`, **Toronto Stock Exchange**: definition "The Toronto Stock Exchange, Canada's main exchange
     for senior companies, with the market identifier code XTSE." Body: "Many of Canada's largest companies are listed
     there, and some are also listed in the United States under a US ticker symbol. See `[listing venue](#listing-venue)`
     and `[SEC EDGAR ticker list](#sec-ticker-list)`."
   - `listing-venue-tsxv`, **TSX Venture Exchange**: definition "The TSX Venture Exchange, a Canadian exchange for
     early-stage and smaller companies, with the market identifier code XTSX." Body: "Its companies are usually smaller
     and trade less often than those on the Toronto Stock Exchange, and few of them file with the SEC. See `[listing venue](#listing-venue)` and `[SEC EDGAR ticker list](#sec-ticker-list)`."
   - `listing-venue-cboe-canada`, **Cboe Canada**: definition "Cboe Canada, a Canadian exchange formerly called the NEO
     Exchange, with the market identifier code NEOE." Body: "It lists companies and many exchange-traded funds. See
     `[listing venue](#listing-venue)` and `[SEC EDGAR ticker list](#sec-ticker-list)`."
   - `listing-venue-cse`, **Canadian Securities Exchange**: definition "The Canadian Securities Exchange, a Canadian
     exchange for smaller and emerging companies, with the market identifier code XCNQ." Body: "Its companies are
     usually small, and few of them file with the SEC. See `[listing venue](#listing-venue)` and `[SEC EDGAR ticker list](#sec-ticker-list)`."
   - Links to `sec-ticker-list`: append "Which companies it lists is explained in `[SEC EDGAR ticker list](#sec-ticker-list)`." to EDGAR's body; append "A ticker that is not in SEC EDGAR's ticker list is the common
     case for an analysis that reads SEC filings; see `[SEC EDGAR ticker list](#sec-ticker-list)`." to Provider Returned
     No Data; and append "It reads the company's financial statements from SEC filings; see `[SEC EDGAR ticker list](#sec-ticker-list)`." to the Graham Number Strategy, Graham Growth Value Strategy, Free Cash Flow & Earnings
     Growth Strategy and Piotroski strategy entries. Add the four venues to the list in Listing Venue's last paragraph.
   - Regenerate the help bundle (`uv run python -m scripts.generate_help`) and the schemas. Update `docs/user/API.md`
     (warning codes and venue codes lists) and `docs/user/WORKSPACE.md` (warning list) to name the new code and venues.
   - Check: slice check (served documents changed).
8. **Smoke checks.** Run the acceptance checks below. For checks 2 and 3, copy the `SEC_USER_AGENT` line of the `.env` file in the owner's real
   settings folder into `.tmp/api-23/config/.env` (create the folder); never print the value, and never commit it.
9. **Finish.** Slice check, commit with the PR title, push the branch, report. After the spec author's clean review,
   open the pull request with the PR text.

## Norms and safeguards

- Escalate by the table in [`AGENTS.md` §11](../../../../../../AGENTS.md#escalation-in-a-spec-driven-unit).
- No new dependency; no `pyproject.toml` or `uv.lock` change; no database migration; no stored shape or version
  change (C3). A step that seems to need one is an escalation.
- Investor-facing text (glossary, messages) does not use "the engine", "a provider" or "the provider" (the project
  owner's wording rule, issue #305). The existing entries this unit only links from keep their text.
- Live captures in step 6 are read-only, at most a few requests per ticker, never in a test.
- No AI or tool attribution in commits, the branch, the pull request or files (`AGENTS.md` §3).
- Issue #116 evidence: stop and keep it (§10).
- Particular to this unit: if `lists_ticker` cannot be added without changing `_resolve_cik`'s behavior, or the entry
  check would make more than one request for SEC's ticker file per add, escalate.

## Acceptance checks

All `ian` commands run from the repository root with `IAN_CONFIG_DIR`, `IAN_DATA_DIR` and `IAN_LOG_DIR` set under
`.tmp/api-23/` in the same invocation (AGENTS.md §10), after `uv run ian database init` if the command asks for it.

1. The slice check passes; `git --no-pager diff --stat origin/main...HEAD` lists only allowed files.
2. `uv run ian graham-number NTR.TO --json` with an SEC identity set up: `status` `input_unavailable`, `reason_code`
   `provider_no_data`, `reason` starting "SEC EDGAR's ticker list does not include NTR.TO, so " and ending "SEC EDGAR
   lists companies under their US ticker symbols only."
3. `uv run ian watchlist create "CA test"`, then `uv run ian watchlist add-selection graham-number "CA test" NTR.TO
   --json`: `warnings` holds one item with `code` `ticker_not_in_sec_list`, `reason_code` null, `arguments.strategies`
   "Graham Number", and `message` equal to C6's template filled in. The same command without `--json` and with a new
   ticker, `uv run ian watchlist add-selection piotroski "CA test" SHOP.TO`, prints the warning under `Warnings:`.
   `uv run ian watchlist add-selection momentum "CA test" BCE.TO --json` gives an empty `warnings`.
4. `uv run ian instrument show NTR.TO --lookup --json`: `listing_venue.code` is `tsx` when step 6 captured Yahoo's
   value for NTR.TO; the text form prints "Listing venue: Toronto Stock Exchange (Toronto)" when the captured value is
   `Toronto`.
5. `uv run ian graham-number MSFT --json`: `status` and `reason_code` equal to the same command on `main` (a listed
   ticker is not affected).
6. Without an SEC identity (checks 2 and 3 with the identity removed from the `.tmp/api-23/` config): check 3 gives no
   `ticker_not_in_sec_list` warning. The API path is covered by `tests/api/test_entry_warnings.py`.

If the owner's real profile has no SEC identity, checks 2 and 3 are run with the tests' stubs only, and the report says
so.

## Report

Commit hash; `git --no-pager diff --stat origin/main...HEAD`; the last slice-check result with its `gate-output.txt`
path; each acceptance check's result with the relevant output lines; the step 6 captures and MIC check; every test file
changed outside the named ones, with why; every escalation with its table row; and a "Pilot measures" line with the
counts the [spec workflow §7](../../../../SPEC_WORKFLOW.md#7-pilot) asks for.

## PR text

Title: `feat(api): explain and warn when SEC EDGAR's ticker list lacks a ticker (API.23)`

Description:

```markdown
Makes it clear why the strategies that read SEC filings are unavailable for a ticker that SEC EDGAR's ticker list
does not include, such as NTR.TO (Nutrien on the Toronto Stock Exchange), and records the plan for Canadian listings.

## What changes for a user

- The reason of such a run names what could not be read: "SEC EDGAR's ticker list does not include NTR.TO, so
  earnings per share could not be read from SEC filings. SEC EDGAR lists companies under their US ticker symbols
  only." New runs only; saved runs keep their reason.
- Adding such a ticker to a watchlist with a strategy that reads SEC filings gives a new warning,
  `ticker_not_in_sec_list`, naming the strategies that will be unavailable. The entry is still added. New warning code
  inside `/v1` (an addition).
- Toronto Stock Exchange, TSX Venture Exchange, Cboe Canada and Canadian Securities Exchange are named listing venues
  (new `ListingVenue` codes, an addition), each captured live and recorded in the mapping record.
- New glossary entries: SEC EDGAR Ticker List, Ticker Not in SEC EDGAR's List, and the four Canadian venues; links to
  the ticker-list entry from EDGAR, Provider Returned No Data and the strategies that read SEC filings.

## For contributors

- Each strategy's behavior bundle declares `reads_sec_edgar` for a selection; the generator emits it for new
  strategies.
- The SEC adapter gains `lists_ticker`.
- No stored shape, version, migration or dependency change.

## Records

- API plan: API.23 and record A.20; API.24 (explain why a result has no number, #306) and record A.21, planned.
- v0.2 implementation plan: work package CAN (Canadian listings, #301), row 15B, and the engine order from
  2026-11-25. Step 3.5's 3.5.5 now follows that order.

Closes #302
```

## Records to add

Step 1 appends these two records to the API plan's Appendix A, after A.19, exactly as written here.

```markdown
### A.20 SEC EDGAR ticker coverage, explained and warned (2026-11-25)

Approved by the project owner on 2026-11-25, as decisions C1 to C22 of one list that also planned the Canadian-listings
work package and the engine order. Closes engine issue 302. Umbrella for Canadian listings: engine issue 301.

| # | Decision |
| :--- | :--- |
| C1 | A new investor glossary entry, SEC EDGAR Ticker List (`sec-ticker-list`): SEC's list of the companies that file with it, each under its US ticker symbol, so a ticker on an exchange outside the United States, such as NTR.TO, is not in it even when the company files with the SEC (Nutrien is NTR on the New York Stock Exchange). Linked from EDGAR, Provider Returned No Data, the entry of each strategy that reads SEC filings, the new warning's entry and each Canadian venue entry. Rejected: extending the EDGAR entry, which would mix what EDGAR is with which companies it lists. |
| C2 | The reason of a run stopped because SEC's ticker list does not include the ticker reads "SEC EDGAR's ticker list does not include {ticker}, so {input} could not be read from SEC filings. SEC EDGAR lists companies under their US ticker symbols only.", where `{input}` is the label of the required input that needed the company identifier, which the failure record already carries. One template for every strategy that reads SEC filings. Amends the message of [A.16](#a16-provider-no-data-is-an-unavailable-input-2026-11-21) E7 and E13 for this case only; a `ticker_unlisted` failure of another provider keeps its message. |
| C3 | New runs get C2's message; stored runs keep theirs, since runs are append-only. No method, result-schema, evidence-codec or document version changes: the status, reason code, failure element and every shape stay the same. |
| C4 | Each strategy declares in its behavior bundle a predicate saying whether a selection reads SEC EDGAR. A selection that supplies every filing input as an override does not (Graham Number with both EPS and book value per share overridden, Graham Growth with EPS overridden); Momentum never does. Rejected: one flag per strategy, which would warn wrongly for fully overridden selections. |
| C5 | A new entry warning, `ticker_not_in_sec_list`, an addition to the open warning-code vocabulary within `/v1`, with its own glossary entry. It is given when the add-entries check identified the ticker, an SEC identity is set up, at least one entry just added for the ticker reads SEC EDGAR, and SEC's ticker file, once loaded, lists no such ticker and no CIK override names it. At most one warning per ticker; `reason_code` null; the entry is never refused. A failure while asking SEC gives no warning and does not stop the check. |
| C6 | Its message: "{ticker} is not in SEC EDGAR's ticker list, so {strategies} will be unavailable for it: they read the company's financial statements from SEC filings. SEC EDGAR lists a company only under its US ticker symbol, so a ticker on an exchange outside the United States is not in the list even when the company files with the SEC." `{strategies}` joins the labels of the affected entries' strategies. |
| C7 | With no SEC identity set up, no new warning: SEC's list cannot be asked, and the strategies report the missing identity themselves. |
| C8 | No warning before a direct analysis; its result carries C2's reason. Same reasoning as [A.14](#a14-ticker-check-on-adding-entries-duplicate-wording-and-provider-statuses-2026-11-20) P2. |
| C9 | Listing-venue codes `tsx`, `tsxv`, `cboe_canada` and `cse` for the Toronto Stock Exchange, TSX Venture Exchange, Cboe Canada and Canadian Securities Exchange, each mapped only from Yahoo values captured live and recorded in the [mapping record](API_22_LISTING_VENUE_MAPPING_RECORD.md), each with an investor glossary entry linking `sec-ticker-list`. New codes are additions under [A.19](#a19-listing-venue-codes-2026-11-23) V9. |
| C10 | The command line prints the new warning as it prints the others ([A.14](#a14-ticker-check-on-adding-entries-duplicate-wording-and-provider-statuses-2026-11-20) P9). |
| C11 | No desktop change in this slice; the desktop repository re-vendors and shows the warning and venue names in its own work. |
| C12 | A new v0.2 work package, `CAN` (Canadian listings), row 15B of the [implementation plan](../IMPLEMENTATION_PLAN.md#sequence-and-status), with its own plan written by CAN.0. Milestone v0.4's Step 5 in the [Master Plan](../../../MASTER_PLAN.md#step-5-localization-engine-for-canadian-markets-en-ca--fr-ca) stays language and number formatting; CAN.0 adds a line there pointing to CAN for Canadian market data, and names CAN in the [Evidence Provider Roadmap](../../../EVIDENCE_PROVIDER_ROADMAP.md)'s security-identity row. |
| C13 | Order of coverage. First, a Canadian-listed ticker whose company files annual reports with the SEC (10-K, 20-F or 40-F), which covers most large companies on the Toronto Stock Exchange. Companies that file only in Canada are researched in CAN.0 with no commitment until a data source is approved (C17). |
| C14 | Slices. CAN.0: evidence and plan, documentation only (captures for about ten issuers, linking methods, the currency-rate source and its licence, a survey of sources for companies that do not file with the SEC, and how many targets file under IFRS). CAN.1: link a Canadian ticker to its SEC filer, so the strategies that read financial facts run; price comparisons stay suppressed where currencies differ; folds in engine issue 293. CAN.2: currency conversion for price comparisons, which also serves US listings of companies that report in Canadian dollars. CAN.3, only if approved later: a source for companies that do not file with the SEC. CAN.0 places engine issue 294 (IFRS book value per share) from its IFRS count. |
| C15 | Linking a Canadian ticker to its SEC filer is deterministic, never fuzzy name matching (company names already differ between sources). CAN.0 evaluates matching the share-class FIGI of the Canadian and US listings through OpenFIGI, a reviewed link table built from captured evidence, and a link the investor declares, including the existing CIK override file. The link and its evidence show in the instrument profile; like today's identity, it is current only. |
| C16 | Never compare across currencies without conversion. CAN.2 converts with an official, free, point-in-time rate whose publication time is known and recorded in provenance; Bank of Canada daily rates are the first candidate, its licence confirmed in CAN.0. A new outbound host goes through the guarded-egress rule with its own decision. |
| C17 | No source is chosen for companies that do not file with the SEC. CAN.0 surveys candidates (licence for local use, cost, point-in-time, coverage) and brings a separate decision; until then those tickers get C1's and C9's explanation. |
| C18 | Engine order from 2026-11-25: API.23, engine issue 304 (fast lane), engine issue 305, API.24, CAN.0, CAN.1, engine issue 307, API.20 and API.21, CAN.2, then Step 3.5's 3.5.5 and 3.5.4 as planned. |
| C19 | 3.5.5 follows CAN.2; [A.15](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a15-355-before-354-2026-11-02) (3.5.5 before 3.5.4) is unchanged. |
| C20 | New investor text in this slice follows engine issue 305's wording rule (no "the engine", no "the provider"); issue 305 rewords the rest of the glossary. |
| C21 | When this slice merges, the spec-workflow pilot's measures go to the project owner for the adopt, adjust or drop decision of the [spec workflow §7](../../../SPEC_WORKFLOW.md#7-pilot), if it is the third spec-driven unit. |
| C22 | Recording: API.23 and API.24, and records A.20 and A.21, in this plan; work package CAN and the engine order in the implementation plan's `CAN` entry; one line in Step 3.5's sequence. |

### A.21 Explain why a result has no number (2026-11-25)

Approved by the project owner on 2026-11-25, as decisions C23 to C31, after a Graham Number run for MSFT read
"Book value per share is unavailable: The preferred share count could not be resolved: Provider returned no data for
the requested field. Missing preferred-share data is not assumed to be zero." Built by API.24; engine issue 306.

| # | Decision |
| :--- | :--- |
| C23 | Every result without a number (`input_unavailable`, `not_applicable` and the provider-failure statuses, every strategy) gets an explanation beside its short reason, in up to four parts: what the method needs (the input and why the method uses it), what was found (what the named data source had), why there is no number (the guess the method declines to make, and why a guessed number would mislead), and what the investor can do (an override, another strategy, checking the ticker, or nothing). |
| C24 | The explanation is built when a document or text is produced, from the stored structured fields (reason code, failed input, failed component where the trace records it, data source, failure kind), never from message text. It is an additive `explanation` part of each strategy's run document and appears in the command-line text; each document's `schema_version` goes up by one. No stored result, evidence codec, method or result-schema version changes, so saved runs get the explanation too. |
| C25 | Where the stored structure is not specific enough, the explanation falls back to the reason-code level, still in four parts. Adding structure to new results is a separate decision, never done by reading text. |
| C26 | API.24's spec catalogues every combination of status, reason code and input each strategy produces, with its explanation; a test fails when a combination has none, so every later strategy ships with explanations. |
| C27 | Investor wording only: no "resolved", "provider", "field" or "the engine"; the data source by name. The shared resolver's "Provider returned no data for the requested field." is reworded for new runs to name the source and the input. |
| C28 | A new investor glossary entry, Why a Result Can Be Unavailable (`unavailable-by-design`): an analysis gives no number rather than one built on a guess, and an unavailable result is information about the company's filings, not a fault. Linked from the Unavailable outcome entry and from every explanation. |
| C29 | Example voice, for MSFT: needs "Book value per share is stockholders' equity, less any preferred stock, divided by the common share count."; found "Microsoft's SEC filings do not report a preferred share count."; no number "A company that has no preferred stock often does not report the count at all, but a missing count can also hide preferred stock that should be subtracted. Assuming zero could overstate book value, so the Graham Number is not calculated."; you can "If you know the book value per share, enter it as an override and run the analysis again." Final texts are in API.24's spec. |
| C30 | The desktop application shows the explanation under the reason after re-vendoring, in its own work. |
| C31 | Explaining is not enough where the gap is in coverage: engine issue 307 asks for a third verified evidence path for zero preferred shares (for example a filing's balance sheet with no preferred stock line, or a reported preferred stock value of zero), captured on MSFT and similar filers, never assumed from absence. It follows CAN.1. |
```

## Change log

- 2026-11-25: links in steps 1 and 7 that are text to paste into other files are written as code spans, because the documentation link check resolved them against this spec (implementer escalation, step 1).
- 2026-11-25: step 2 gains a wording for an empty `what`, so no call site can print a blank input (implementer observation on FCF Growth's scope-failure site, step 2).
- 2026-11-25: allowed files gain the two generator tests and a new `selection.py.fill`, which the new behavior-bundle member needs as `STRATEGY_DEVELOPMENT.md`'s platform-change checklist says (implementer escalation, step 3).
