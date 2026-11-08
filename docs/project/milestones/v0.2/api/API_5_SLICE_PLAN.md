# API.5 — Slice Plan: Help Content

Splits [API.5](API_CONTRACT_AND_SLICE_PLAN.md#api5a--help-content-the-glossary) into two slices
([H1](#h1-api5-is-split-in-two-2026-11-07)). The first restructures the glossary so that each entry can be served on its
own: three audiences, a permanent id and a short definition for every entry, and a checker. The second packages the served
content and is split again ([H23](#h23-api5b-is-split-in-two-2026-11-07)): API.5b1 makes the served guides
interface-neutral and checks them, and API.5b2 packages the served content as a generated help bundle.

## 1. At a glance

- **What this plan does:**
  - API.5a splits the glossary into investor terms, command-line terms and contributor terms, gives every entry an id and
    every entry a short definition, rewrites every link to a glossary entry to target the id, and adds
    `scripts/check_help_content.py` as a gate step;
  - API.5b1 makes every served section interface-neutral, marks the command-line parts of the served guides as excluded,
    retires `strategies/GRAHAM.md`, and checks served content for commands and for links to what is not served;
  - API.5b2 adds the `help` package with the generated bundle, its loader and its drift check.
- **What it does not do:** serve anything over HTTP, add a term for a run outcome, a status or a reason code, or change a
  formula, a stored shape or a dependency. The endpoints and the term references are
  [API.6](API_CONTRACT_AND_SLICE_PLAN.md#api6a--term-references).
- **Rules every slice follows:**
  - Markdown stays the source of every explanation;
  - an investor entry is interface-neutral and depends on no contributor or command-line term;
  - the managed quality gate, with the Python 3.14 second pass, after each slice, and the project owner's approval before the
    next slice starts.
- **Where the history lives:** decisions H1 to H15 are in [Appendix A](#appendix-a-decision-records), approved by the
  project owner on 2026-11-07, and H16 to H22 are the review fixes of API.5a, approved the same day. H11 to H14 decide
  the checks on the guides and the bundle and are not implemented by API.5a. H23 to H35 split API.5b and decide API.5b1
  and API.5b2, approved the same day; API.5b1 implements H23 to H30, H34 and H35, and H31 to H33 are API.5b2's. H36 to H39 are the review fixes of API.5b1,
  approved the same day. H40 to H55 complete API.5b2 and amend H31 to H33, approved the same day; H54 and H55 are
  contract decisions for API.6. H56 to H60 are the review fixes of API.5b2, approved the same day.

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.5a | [The glossary](#api5a--the-glossary) | Complete | 2026-11-07 |
| API.5b1 | [The guides](#api5b1--the-guides) | Complete | 2026-11-07 |
| API.5b2 | [The bundle](#api5b2--the-bundle) | Complete | 2026-11-07 |

## 3. The slices

### API.5a — The glossary

- **Problem:** the glossary mixes investor, command-line and contributor terms; many entries have no first paragraph that
  stands alone; nothing gives a term a stable identifier; and an entry's heading slug changes whenever it is reworded.
- **Decision:**
  - three audiences ([H3](#h3-three-audiences-2026-11-07)) and interface-neutral investor entries
    ([H4](#h4-investor-entries-are-interface-neutral-2026-11-07));
  - a permanent id per entry, which every link targets ([H5](#h5-term-ids-2026-11-07),
    [H6](#h6-names-and-combined-entries-2026-11-07));
  - a short definition as the first paragraph ([H7](#h7-the-short-definition-2026-11-07));
  - cleanup ([H8](#h8-cleanup-2026-11-07), [H20](#h20-unused-entries-2026-11-07)), the boundary with API.6 ([H9](#h9-boundary-with-api6-2026-11-07)) and the
    exclude marker ([H10](#h10-the-exclude-marker-2026-11-07));
  - one checker, a gate step ([H15](#h15-scripts-2026-11-07)), and the review fixes
    [H16](#h16-sentence-where-actual-sentences-are-counted-2026-11-07) to [H22](#h22-the-review-basis-2026-11-07).
- **Scope:** `docs/user/GLOSSARY.md`; `docs/project/CONTRIBUTOR_GLOSSARY.md`; `scripts/check_help_content.py` and
  `scripts/check_doc_links.py`, with tests; every link into the glossary; the strategy guides' glossary links;
  `WORKSPACE.md`; `docs/project/README.md`, `docs/user/README.md` and `AGENTS.md` pointers; both gate wrappers and the CI
  workflow; this plan and the contract.
- **Branch:** `feat/api-help-glossary`.
- **Detail:** [Implementation record](#31-api5a-implementation-record).

### API.5b1 — The guides

- **Problem:** the served guides mix explanation with command-line instructions, flags, environment variables, exit codes
  and links to documents that are not served, so none of them can be served as it stands.
- **Decision:**
  - every served section is interface-neutral ([H24](#h24-served-sections-are-interface-neutral-2026-11-07)), and command-line
    material stays in its guide in excluded sections ([H25](#h25-command-line-material-stays-in-its-guide-2026-11-07));
  - `strategies/GRAHAM.md` is retired ([H26](#h26-retiring-strategiesgrahammd-2026-11-07));
  - leak checks on served content ([H27](#h27-the-leak-rules-2026-11-07),
    [H28](#h28-command-names-in-code-spans-2026-11-07), [H29](#h29-where-the-served-content-checks-live-2026-11-07)),
    which extend [H11](#h11-leak-checks-on-served-content-2026-11-07) and [H12](#h12-served-documents-2026-11-07);
  - the Beginner Guide ([H30](#h30-the-beginner-guide-2026-11-07)) and the contributor guide's `guide` edit site
    ([H34](#h34-the-contributor-guides-guide-edit-site-2026-11-07)).
- **Scope:** the Beginner Guide, `FINANCE_MATH.md` and the five strategy guides; `strategies/GRAHAM.md` retired and every link
  to it retargeted; `scripts/check_help_content.py` and its tests; `tests/scripts/test_served_content.py`;
  `scripts/strategy_sites.toml` and the regenerated edit-site table; this plan and the contract.
- **Branch:** `feat/api-help-guides`.
- **Detail:** [Implementation record](#32-api5b1-implementation-record).

### API.5b2 — The bundle

- **Problem:** nothing packages the served content for the API.
- **Decision:**
  - the bundle ([H13](#h13-the-bundle-2026-11-07), amended by [H32](#h32-a-loader-now-2026-11-07)), links in it
    ([H14](#h14-links-in-the-bundle-2026-11-07)), its shape ([H31](#h31-the-bundles-shape-2026-11-07)) and its generator and
    drift check ([H33](#h33-generator-and-drift-2026-11-07));
  - the plan, package, model, loader, integrity checks, text forms, rewriting, refusal, installed-package check, gate and
    documents ([H40](#h40-plan-records-2026-11-07) to [H53](#h53-architecture-2026-11-07));
  - which references are stable across locales ([H54](#h54-stable-references-across-locales-2026-11-07)) and how API.6 chooses
    a locale ([H55](#h55-locale-choice-2026-11-07)).
- **Scope:** the `help` package with the bundle model, its loader and `help_bundle.json`; the generator
  `scripts/generate_help.py` and its drift check; package-data; Architecture §13; `check_installed_package`; the gate wiring.
- **Branch:** `feat/api-help-bundle`.
- **Detail:** [Implementation record](#33-api5b2-implementation-record).

### 3.1 API.5a implementation record

What changed, by area:

- **Glossaries:**
  - `docs/user/GLOSSARY.md` holds the investor entries and, in its last section (which carries the exclude marker), the
    command-line terms: CLI, API, JSON, Machine-Readable Output, UUID, SQLite, Light Mode, Full Dual-Tier Mode and LLM
    (the owner moved LLM there on 2026-11-07), and OHLCV is a contributor term ([H20](#h20-unused-entries-2026-11-07));
  - `docs/project/CONTRIBUTOR_GLOSSARY.md` holds the contributor terms: BaseAnalyzer, Method Discriminator, Discriminated
    Union, Input-Resolution Layer, Resolved Input, Heterogeneous Strategy Independence, BaseDataClient, Fixture Adapter,
    Fixture, Production Persistence, the Evaluation section, Trajectory Telemetry, Operational Logging, Circuit Breaker, WAL,
    CI, DAO, DI, PR, Pydantic, SQL and JSONL.
- **Removed or merged:**
  - Sharpe Ratio: removed, named by [H8](#h8-cleanup-2026-11-07); the link to it in the Momentum guide is plain text;
  - Historical EPS CAGR Proxy: removed under the owner's ruling on unused entries; it describes something the engine does
    not implement and nothing else mentions it;
  - the two Industry class entries: merged into one that links to As-filed SIC code;
  - the MOS acronym entry: merged into Margin of Safety (MOS), which already held the definition;
  - Basis Point: removed, because nothing in the documents or the code uses it ([H20](#h20-unused-entries-2026-11-07));
  - Momentum Analyzer: renamed Momentum Strategy ([H8](#h8-cleanup-2026-11-07), amended), in the glossary, the Momentum
    guide's title, `FINANCE_MATH.md`'s heading and every mention in `docs/user` and `README.md`; the id `momentum-strategy`
    is unchanged and historical milestone plans keep the old name;
  - the sections group terms by use, and each strategy's entry leads its own section
    ([H17](#h17-sections-group-terms-by-where-they-are-used-2026-11-07)); the lone General terms section is dissolved.
- **Moved to the user documents (H4):** the `--workers` bound, the 1-based entry numbering and the `runs show` and
  `runs compare` use of a headline were already in `WORKSPACE.md`; the one missing sentence, that removing an entry
  renumbers the entries after it, is added there. The `--expected-growth` and `--aaa-yield` flags are in the Graham Growth
  guide. The closed list of strategies in Analysis Strategy and Headline, and the "every strategy currently implemented has
  exactly one" count in Method, were dropped, not moved.
- **Links:** every link to a glossary entry in the repository targets the id. The strategy guides' "Related documentation"
  links to a glossary section now target that strategy's own entry id (the owner's ruling).
- **Checkers:**
  - `scripts/check_doc_links.py`: `<a id>` lines are anchors; a link into either glossary must target an id, and a link to a
    heading slug or a section heading is reported;
  - `scripts/check_help_content.py`: the id line, the id form and its uniqueness, an id that is a different entry's heading
    slug, plain-text names, the short-definition limits (200 characters, two sentences, no link, backtick, `*`, `_` or `[`),
    investor entries that link to a contributor or command-line term, and a marker that is not directly after a heading. A
    failure names the file, the line, the entry and the reason.
  - both are standard-library-only gate steps in `scripts/run-quality-gates.sh`, `scripts/run-quality-gates.ps1` and the CI
    workflow, and are listed in `docs/project/README.md`.
- **Review fixes:** names are in Title Case ([H18](#h18-one-naming-style-2026-11-07)); six short definitions are rewritten
  to stand alone ([H19](#h19-short-definitions-that-stand-alone-2026-11-07)); `tests/test_documented_conventions.py` allows
  the phrases `two sentences` and `sentences; the limit`, which count actual sentences
  ([H16](#h16-sentence-where-actual-sentences-are-counted-2026-11-07)); `scripts/check_help_content.py` asks git for the
  repository root once ([H21](#h21-one-repository-root-lookup-2026-11-07)).
- **Gate change found during the review:** a pytest pass recorded how many tests skipped but not which, so two of six skips
  could only be inferred. Every pytest pass of both wrappers, including the extra-interpreter pass, and the CI test step now
  pass `-rs`, which lists each skipped test by full name with its reason; `docs/project/README.md` says so.
- **Pointers:** a "Glossary entries" section in `docs/project/README.md` states the rules; `AGENTS.md`, `docs/user/README.md`
  and the project README name both glossaries.
- **Tests:** `tests/scripts/test_check_help_content.py` and `tests/scripts/test_check_doc_links_glossary.py`.

Noticed for later slices: whether a short definition stands alone is a review rule, not a checked one; API.6 adds the terms
for run outcomes, statuses and reason codes when its conformance test needs them.

### 3.2 API.5b1 implementation record

What changed, by area:

- **Served documents:** the Beginner Guide, `FINANCE_MATH.md`, the user glossary and the five strategy guides
  ([H29](#h29-where-the-served-content-checks-live-2026-11-07)). The glossary needed no change; the checker found no leak in
  it.
- **Guides:**
  - every strategy guide marks its Quick start, Watchlist options and Related documentation as excluded sections, and the
    guides that have them mark Command options and Presentation modes;
  - a mixed section keeps its explanation as served text and ends with an excluded "On the command line" subsection that
    holds its flags, shell examples, cache-bypass instructions and output-mode pointers
    ([H25](#h25-command-line-material-stays-in-its-guide-2026-11-07));
  - explanation that sat inside a Quick start or Presentation modes section moved to the served section it explains: the
    Graham guides' quote-reuse and provenance paragraphs are under Data sources, the FCF default policy has a section of its
    own, and the Piotroski comparison cells are under Reading the result;
  - the Beginner Guide lists a few illustrative strategies, links no unserved document, and its first steps are excluded
    ([H30](#h30-the-beginner-guide-2026-11-07)); `FINANCE_MATH.md` has two reworded sentences and no link to an unserved
    document.
- **Momentum statuses:** "Statuses and failures" is a served section: the status table without an exit-code column, the
  reason and reason code, the fixed provider-failure reason, and the saved and refreshed outcome. Its final "On the command
  line" subsection holds the exit codes, the missing result part in `--json`, standard error, the provider check, `--save-run`,
  the refresh exit code and the rejection of a wrong request ([H36](#h36-momentums-statuses-and-failures-are-served-2026-11-07)).
- **Project README:** a "Served documents" section after "Glossary entries" states the served documents and the rules, with
  links to H24, H25, H27 and H28, and the documentation-only gate names `tests/scripts/test_served_content.py`
  ([H37](#h37-the-served-document-rules-are-documented-now-2026-11-07)).
- **`strategies/GRAHAM.md`:** deleted. Its Point-in-time section is in both Graham guides, with the explanation served and the
  `--as-of` examples in an "On the command line" subsection; its Presentation modes section is an excluded section of both
  guides; its two summary sections are dropped. Every link to it is retargeted, and `strategies/README.md` lists the two
  Graham guides as peers ([H26](#h26-retiring-strategiesgrahammd-2026-11-07)). Historical plans keep the name in plain text.
- **Checker:** `scripts/check_help_content.py` stays standard-library-only and gains the leak rules of
  [H27](#h27-the-leak-rules-2026-11-07), the rule that an "On the command line" heading carries the marker and is the last
  subsection of its parent, and a public parser of served content (`served_documents`, `served_document`, `code_spans`,
  `strategy_guide_paths`). A failure names the file, the line, the section heading and the reason.
- **Tests:** `tests/scripts/test_check_help_content.py` gains a failing and a passing case for each rule;
  `tests/scripts/test_served_content.py` reads the command names from the Typer application and pins one served guide per
  strategy ([H28](#h28-command-names-in-code-spans-2026-11-07)). No other test changed.
- **Edit site:** the `guide` site in `scripts/strategy_sites.toml` says what a guide must do
  ([H34](#h34-the-contributor-guides-guide-edit-site-2026-11-07)); the edit-site table in `docs/TOOL_DEVELOPMENT.md` is
  regenerated.

Judgment calls, each a place where the decisions left a choice:

- Only top-level command and group names are matched by the code-span test: a subcommand is reached through its group, and
  the subcommand names `status` and `list` are ordinary words that served text puts in code spans (`status = unavailable`).
- The FCF guide's forward-policy table names the policies as the typed model does (`display_only`, `hard_gate`), and the
  hyphenated option values are in the "On the command line" subsection.
- A strategy's settings file name and its link to the installation guide are in an "On the command line" subsection.
- The sentence "Machine-readable JSON uses `null` for unavailable numeric outputs" stays in the Momentum guide and in
  `FINANCE_MATH.md`: it names neither a flag nor a mode, and the API returns JSON too.

Noticed for later slices:

- API.5b2's generator takes its sections from `served_documents`, and a section's id is its `slug`, which counts excluded
  headings as GitHub does.
- A link into the user glossary from served content must target the id of a served term, so a "Related documentation" list
  that links the glossary as a whole is excluded and the Beginner Guide's "Further reading" no longer lists it.

### 3.3 API.5b2 implementation record

What changed, by area:

- **Package:** `investment_analysis_engine/help/` holds `bundle.py` and the generated `help_bundle.json`, and its
  `__init__.py` holds only a docstring ([H41](#h41-package-layout-2026-11-07)). `bundle.py` has the frozen models
  `HelpBundle`, `HelpTerm`, `HelpGroup`, `HelpDocument` and `HelpSection`, the cached `load_help_bundle()`
  ([H42](#h42-model-and-loader-2026-11-07)) and the integrity validator
  ([H43](#h43-integrity-is-checked-by-the-model-2026-11-07)). Nothing imports it yet.
- **Generator:** `scripts/generate_help.py` mirrors `scripts/generate_openapi.py`. It runs the whole checker first,
  `check_repository` and `check_served_content`, and stops with every problem when there is one
  ([H48](#h48-generator-refusal-2026-11-07), amended by [H57](#h57-the-generator-runs-the-whole-checker-2026-11-07)), builds the bundle through
  `HelpBundle`, and writes it in the form of [H51](#h51-json-text-2026-11-07). A term is an investor entry of the user
  glossary: its short definition is the first paragraph and its body the rest ([H46](#h46-trimming-2026-11-07)). A
  document's title and introduction are its level-1 heading and the text under it, and its sections are every served heading
  below level 1 ([H45](#h45-title-and-introduction-2026-11-07)). Links are rewritten by the table of
  [H47](#h47-link-rewriting-2026-11-07); a link that fits no row stops the generator, naming the file, the line and the
  target. A group is a level-2 section of the glossary, with the heading slug as its id
  ([H44](#h44-group-ids-2026-11-07)).
- **Shared parser ([H56](#h56-one-parser-for-served-content-2026-11-07)):** the generator has no parser of its own.
  `scripts/check_help_content.py` makes its fence, heading, code-span, link and scheme patterns public (`FENCE_RE`,
  `HEADING_RE`, `CODE_SPAN_RE`, `LINK_RE`, `SCHEME_RE`), and `ServedDocument` gains `groups`, a tuple of `ServedGroup`
  (heading, line, slug, excluded) for the level-2 headings of the user glossary, empty for every other document. The
  checker's messages and results are unchanged, except for the new rule of
  [H57](#h57-the-generator-runs-the-whole-checker-2026-11-07): a served document has exactly one level-1 heading.
- **Installed package:** `scripts/check_installed_package.py` prints the installed `load_help_bundle()` result as JSON and
  compares it with the repository's `help_bundle.json` loaded through `HelpBundle`, as a whole
  ([H49](#h49-installed-package-check-amends-h32-2026-11-07)). `help/help_bundle.json` is in package-data.
- **Gate:** `generate_help --check` is a step of both wrappers after `generate_openapi --check`, and a step of the CI
  `quality-and-test` job, which also runs `generate_openapi --check` directly before it
  ([H58](#h58-ci-checks-openapijson-for-drift-2026-11-07)). `docs/project/README.md` lists both among the gate's commands, names it for a change to a served
  document and says to regenerate the bundle after editing one ([H50](#h50-contributor-gate-and-docs-2026-11-07));
  `AGENTS.md` §7 points at that section; the `guide` site of `scripts/strategy_sites.toml` says the bundle is regenerated,
  and the edit-site table in `docs/TOOL_DEVELOPMENT.md` is regenerated.
- **Architecture:** §13 has a `help` row at layer 0 with no imports ([H53](#h53-architecture-2026-11-07)).
- **Tests:** `tests/scripts/test_generate_help.py`, `tests/help/test_bundle.py` and an addition to
  `tests/scripts/test_check_installed_package.py` ([H52](#h52-tests-2026-11-07)).

Judgment calls, each a place where the decisions left a choice:

- `slugify` is imported from `scripts/check_doc_links.py`, the module that defines it, not through
  `scripts/check_help_content.py`, which only imports it.
- A glossary section with no served entry is left out of `groups`, so a client's group list never shows an empty group.
  Today none is empty.
- The first version of this slice put `generate_help --check` in the `quality-and-test` job before the Ruff format check,
  because the CI workflow had no `generate_openapi --check` step; [H58](#h58-ci-checks-openapijson-for-drift-2026-11-07)
  adds that step and the README line before it.
- The sequence tables date API.5b2 with the day the branch was finished; the pull request, when opened, keeps that date
  unless it opens later.

Noticed for later slices:

- API.6 adds the `api` import of `help` and decides whether the bundle has one file per locale
  ([H55](#h55-locale-choice-2026-11-07)); the loader reads one file today.
- 21 terms have no body, only a definition, so a client must render an empty `body` as nothing.
- A link rewritten to `help:documents/<id>` stands for the document's start, whether the source linked the file or its title
  anchor.

## 4. Scope limits and acceptance criteria

- API.5a changes no stored shape, formula, classification, dependency or CLI text, and adds no term for a run outcome, a
  status or a reason code.
- Every entry of both glossaries has an id, and no id repeats within a glossary.
- Every investor entry's first paragraph is at most 200 characters and two sentences, in plain text.
- No investor entry links to a contributor term or a command-line term.
- Every link to a glossary entry targets an id, and the link checker fails one that targets a heading slug.
- `scripts/check_help_content.py` is a step of both wrappers and of CI.
- API.5b1 changes no formula, stored shape, classification, dependency or command-line text; text that moves stays word for
  word except where [H24](#h24-served-sections-are-interface-neutral-2026-11-07) requires rewording.
- API.5b1: served content has no code span that starts with `ian `, `--`, `uv ` or `IAN_`, no code span that starts with the
  name of an `ian` command or group, no fenced block with an `ian` command line or in a shell language, and no link to a
  file that is not served, to an excluded section, to a term that is not served or to the glossary without an entry id; the
  check reports zero findings in the managed gate.
- API.5b1: `strategies/GRAHAM.md` is gone, nothing links to it, and exactly one strategy guide is served for each strategy.
- API.5b2: the help bundle is regenerated and compared in the managed gate, in both wrappers and in CI; a drift fails it,
  and the generator writes nothing while the served-content check reports a problem.
- API.5b2: every term is in exactly one group, every `help:` link in the bundle resolves, the installed package's bundle
  equals the repository's, and no endpoint, `api` import of `help` or locale handling is added.

## 5. Background

The contract ([A.4](API_CONTRACT_AND_SLICE_PLAN.md#a4-help-content-in-the-gui-2026-10-30)) makes the engine the owner of
every explanation a GUI shows. A served term needs a stable identifier and a definition that stands alone, and the glossary
had neither, and held terms an investor never needs. API.5 was one slice with a glossary half and a bundle half; the
glossary half is a large documentation change, so the two are separate pull requests. The bundle half was split again
because rewording and marking every served guide is a large documentation change of its own, and the bundle is easier to
review once the guides it serves are settled.

## Appendix A: Decision records

H1 to H15 were approved by the project owner on 2026-11-07, with the amendments recorded in H3 and H8. H16 to H22 are the review
fixes of API.5a, approved the same day. H23 to H35 split API.5b and decide API.5b1 and API.5b2, approved the same day;
H31 to H33 decide API.5b2 and are recorded here, not implemented by API.5b1. H36 to H39 are the review fixes of
API.5b1, approved the same day. H40 to H55 complete API.5b2 and are approved the same day. H56 to H60 are the review
fixes of API.5b2, approved the same day.

### H1 API.5 is split in two (2026-11-07)

- API.5a, on `feat/api-help-glossary`: the slice plan, the three-way glossary split, term ids and anchors, the short
  definitions, the link rewrite and the entry checker.
- API.5b, on `feat/api-help-bundle`: the exclude markers in the guides, the leak checks on the guides, retiring
  `strategies/GRAHAM.md`, and the `help` package with the bundle generator and its drift check.
- The contract's API.5 row becomes API.5a and API.5b rows, its section is split, and its single `docs/api-help-content`
  branch is replaced by the two branches.
- Amendment ([H23](#h23-api5b-is-split-in-two-2026-11-07)): API.5b is split in two.

### H2 The slice plan (2026-11-07)

- This plan follows the reference structure of the IR plan and the layout of the API.4 plan: scannable, with the driest
  material toward the end and decision records in an appendix.
- API.5a's pull request marks its row Complete, dated the day it is opened. API.5b stays Planned.

### H3 Three audiences (2026-11-07)

- Contributor terms move to `docs/project/CONTRIBUTOR_GLOSSARY.md`: BaseAnalyzer, Method Discriminator, Discriminated Union,
  Input-Resolution Layer, Resolved Input, Heterogeneous Strategy Independence; BaseDataClient, Fixture Adapter, Fixture,
  Production Persistence; the whole Evaluation section; Trajectory Telemetry, Operational Logging, Circuit Breaker, WAL; CI,
  DAO, DI, PR, Pydantic, SQL and JSONL.
- Command-line terms stay in `docs/user/GLOSSARY.md`, in one section that carries the exclude marker: CLI, API, JSON,
  Machine-Readable Output, UUID, SQLite, Light Mode and Full Dual-Tier Mode. Amendment: LLM is in that section too.
- Every other entry is an investor term. Ruling: Typed Evidence, UTC and Applicability Status stay investor terms.
- The contributor glossary may link to investor terms. No investor entry links to a contributor or command-line term.
- `AGENTS.md`'s "Domain terms" pointer, `docs/user/README.md` and `docs/project/README.md` are updated.

### H4 Investor entries are interface-neutral (2026-11-07)

- An investor entry contains no command, flag, command-line output convention or closed list of strategies.
- That material moves to the user document where a command-line user would look for it, normally `USAGE.md` or
  `WORKSPACE.md`. A list of strategies is dropped, not moved. An item with no fitting home stops the slice for a decision.

### H5 Term ids (2026-11-07)

- Every entry in both glossaries has a permanent id: lowercase ASCII words joined by single hyphens, short, chosen per
  entry, written as `<a id="<id>"></a>` on its own line directly above the heading.
- An id is unique within its glossary. It may equal its own entry's heading slug, but not a different entry's heading slug.
- Every inbound link to a glossary entry anywhere in the repository targets the id.
- `scripts/check_doc_links.py` resolves `<a id>` anchors and fails a link into either glossary that targets a heading slug.

### H6 Names and combined entries (2026-11-07)

- A term's name, its heading, is plain text with no code span; the code value may appear in the entry's body.
- A combined heading stays one entry with one id. It is split only when one short definition cannot cover its parts.

### H7 The short definition (2026-11-07)

- An entry's first paragraph is its short definition: at most 200 characters, at most two sentences, plain text with no
  link, backtick, `*`, `_` or `[`. It stands alone, which is a review rule and not a checked one.
- The rest of the entry follows as further paragraphs; formulas and links belong there.
- A definition's meaning stays accurate to `FINANCE_MATH.md` and the code.

### H8 Cleanup (2026-11-07)

- Merge the two Industry class entries into one, linked to the as-filed SIC code entry.
- Rename Momentum Analyzer to Momentum Analysis Strategy and make it consistent with the other strategy entries.
- Remove Sharpe Ratio and any entry that nothing in `docs/user` uses. Ruling: an investor entry stays if a `docs/user` file
  other than the glossary names its concept under any wording, or if another investor entry relies on it to explain itself.
  An entry that describes something the engine does not implement and that nothing else mentions is removed. An unclear
  entry stops the slice for a decision.
- Amendment ([H20](#h20-unused-entries-2026-11-07)): the strategy is named Momentum Strategy, matching every other strategy's
  `<name> Strategy` form, instead of Momentum Analysis Strategy.

### H9 Boundary with API.6 (2026-11-07)

- API.5a restructures existing content only. It adds no term for a run outcome, a status or a reason code; API.6 writes those
  when its conformance test needs them.
- API.6's scope gains an orphan-term check: every served term is referenced by an API.6 mapping or linked from served
  content.

### H10 The exclude marker (2026-11-07)

- `<!-- help:exclude -->` on the line directly after a heading excludes that section and its subsections from served
  content. There are no inline ranges.
- API.5a uses it only on the glossary's command-line section. The checker knows the marker, so that API.5b can use it in the
  guides.

### H11 Leak checks on served content (2026-11-07)

For API.5b. Served content fails the gate on:

- a code span starting with `ian ` or `--`;
- a fenced block with an `ian` command line;
- a link to a repository file that is not served.

An external https link passes. The Beginner Guide's README-disclaimer link becomes an absolute GitHub link.

### H12 Served documents (2026-11-07)

For API.5b.

- The served documents are the Beginner Guide, Finance Math, and one guide per strategy, found from `STRATEGIES`.
- `strategies/GRAHAM.md` is retired: its Point-in-time section moves into both Graham guides.
- Document ids are `beginner-guide`, `finance-math` and each strategy's alias.

### H13 The bundle (2026-11-07)

For API.5b.

- A new layer-0 package, `help`, holds a Pydantic bundle model and the generated `help_bundle.json`.
- The bundle is in package-data, checked by `check_installed_package`, and gets an Architecture §13 row.
- It has no version field. The loader is API.6's work.
- Amendment (H32): the loader is API.5b2's work.

### H14 Links in the bundle (2026-11-07)

For API.5b.

- In-app links are `help:terms/<id>` and `help:documents/<id>#<section-slug>`.
- Section ids are GitHub heading slugs; only term ids are permanent.

### H15 Scripts (2026-11-07)

- `scripts/check_help_content.py`, with tests, checks both glossaries for: an id line above every entry, the id form and its
  uniqueness, plain-text names, the short-definition limits, no investor-to-contributor or investor-to-command-line links,
  and the exclude marker recognized. Its failure messages name the file, the entry and what is wrong.
- It is a gate step wherever `check_doc_links.py` runs: both wrappers, the CI workflow and `docs/project/README.md`'s command
  list.
- `scripts/generate_help.py` is API.5b's work.

### H16 "sentence" where actual sentences are counted (2026-11-07)

- `tests/test_documented_conventions.py` fails on a use of the word that is not in its allowlist. The new uses count actual
  English sentences: the limit of two in a short definition and the checker's message about it.
- Two phrases are added to `_ALLOWED_PHRASES`: `two {w}s` and `{w}s; the limit`. The checker's identifiers that held the word
  are renamed, so no other phrase is needed.

### H17 Sections group terms by where they are used (2026-11-07)

- A section is the term's group in the API.5b bundle. A strategy's section holds only terms that strategy alone uses; every
  other investor term is in a shared topic section. Each strategy's entry leads its own section.
- The sections are: Analysis strategies and results; Local research workspace; Market data and timing; Company financial
  measures; Valuation and price comparison; one section for each of the five strategies; and the excluded Command-line
  terms. The General terms section is dissolved.
- Placements that were judgment calls: Three-Year-Average EPS, used by both Graham strategies, is in Company financial
  measures; Weighted-Average Diluted Shares, used by one strategy, is there as well, as the owner listed it; AAA Rating is in
  Valuation and price comparison, and AAA Corporate Bond Yield is in the Graham Growth Value section; Applicability Status and
  Not Applicable are in Analysis strategies and results; UTC is in Market data and timing.

### H18 One naming style (2026-11-07)

- Every term name in both glossaries is in Title Case. The two code-like names change: PASS / FAIL / INDETERMINATE becomes FCF
  Classification, and Retrieved at becomes Retrieval Time; the code values stay in the bodies. Ids do not change.

### H19 Short definitions that stand alone (2026-11-07)

- The short definitions of Bullish / Bearish / Unknown, RSI, Free Cash Flow, Baseline AAA Yield, Analysis Strategy and
  Momentum Strategy are rewritten in plain words. Strategy-specific detail, such as normalized capital expenditures, moves to
  the entry's body.
- Two proposed wordings changed to match the engine: bearish is "when it is not" above the long average, because an equal pair
  is bearish; and the baseline AAA yield is "4.4 by default", because it is configurable.

### H20 Unused entries (2026-11-07)

- Basis Point is removed. OHLCV moves to the contributor glossary, with its id kept, because it appears in the code and never
  in a user document. The Momentum rename is recorded in H8's amendment.

### H21 One repository-root lookup (2026-11-07)

- `scripts/check_help_content.py` computes the repository root once and reuses it. A new script does the same; the existing
  `scripts/check_doc_links.py` is not changed beyond the glossary rule.

### H22 The review basis (2026-11-07)

- The review relied on the pushed branch at commit 185f7cf. These fixes are a follow-up commit on the same branch.

### H23 API.5b is split in two (2026-11-07)

- API.5b1, on `feat/api-help-guides`: served sections made interface-neutral, the exclude markers, `strategies/GRAHAM.md`
  retired, and the leak checks.
- API.5b2, on `feat/api-help-bundle`: the `help` package, the bundle model, its loader and the generator
  `scripts/generate_help.py`; the drift check; package-data, the Architecture §13 row and `check_installed_package`.
- API.5b1 does none of API.5b2's work. The sequence table has a row for each.

### H24 Served sections are interface-neutral (2026-11-07)

- This extends [H4](#h4-investor-entries-are-interface-neutral-2026-11-07) from the glossary to every served section of every
  served document.
- A served section contains none of these: a command, flag or option; an environment variable; an exit code; a command-line
  output mode (default, `--details`, `--diagnostics`, `--json`).
- It says "an analysis", not "a command". Example: the Beginner Guide's "Some commands also accept user-provided overrides"
  becomes "Some analyses also accept user-provided overrides".
- When a sentence is reworded, its meaning stays accurate to `FINANCE_MATH.md` and the code. Moved text stays word for word
  wherever it does not need rewording.

### H25 Command-line material stays in its guide (2026-11-07)

- A section that is entirely command-line material carries `<!-- help:exclude -->` on the line directly after its heading.
  This includes each guide's Quick start, Command options, Presentation modes, Watchlist options and Related documentation,
  and Momentum's "Status, failures and exit codes" (amended by [H36](#h36-momentums-statuses-and-failures-are-served-2026-11-07): it is served).
- A mixed section keeps its explanation as served text and ends with a subsection one heading level below it, titled exactly
  "On the command line", which carries the marker. It holds that section's flags and options, shell examples, cache-bypass
  instructions and output-mode pointers, and it is the last subsection of its parent.
- Explanation that sits inside a Quick start or another excluded section moves to the served section it explains. Example:
  the Graham Number Quick start's paragraph on quote reuse and retrieval time moves under Data sources.

### H26 Retiring strategies/GRAHAM.md (2026-11-07)

- Its "Point-in-time analysis" section moves into both `GRAHAM_NUMBER.md` and `GRAHAM_GROWTH.md`: the explanation is served and
  the `--as-of` examples go in an "On the command line" subsection.
- Its "Presentation modes" section moves into both Graham guides as an excluded section, replacing their links to
  `GRAHAM.md#presentation-modes`. Its "Graham Number" and "Graham Growth Value" summary sections are dropped.
- The file is deleted and every inbound link is retargeted: in the Beginner Guide, `FINANCE_MATH.md`,
  `docs/user/strategies/README.md` and both Graham guides. The strategy index lists the two Graham guides as peers of the
  other strategy guides. Historical milestone plans that name `GRAHAM.md` in plain text are left as they are.

### H27 The leak rules (2026-11-07)

- Served content fails the check on any of: a code span starting with `ian `, `--`, `uv ` or `IAN_`; a fenced block containing
  an `ian` command line, with or without a `uv run ` prefix; a fenced block whose language is a shell (bash, sh, shell,
  console, powershell, pwsh, ps1 or cmd); a link to a repository file that is not served; a link to an excluded section of a
  served document; a link to a term that is not served, which is a command-line term or any entry of the contributor
  glossary; a link to `docs/user/GLOSSARY.md` with no entry id.
- An external https link passes. The Beginner Guide's README-disclaimer link becomes
  `https://github.com/PeterPontbriand/investment-analysis-engine/blob/main/README.md#limitations--disclaimer`.

### H28 Command names in code spans (2026-11-07)

- A pytest test imports the `ian` Typer application and fails on any code span in served content whose first word is the name of
  an `ian` command or command group. Strategy aliases count, so `graham-number` and `watchlist` are both caught.
- The names are derived from the Typer application at test time, never from a hand-kept list.

### H29 Where the served-content checks live (2026-11-07)

- `scripts/check_help_content.py` stays standard-library-only and gains the H27 checks. It finds the served documents as
  `docs/user/BEGINNER_GUIDE.md`, `docs/user/FINANCE_MATH.md`, `docs/user/GLOSSARY.md` and every `docs/user/strategies/*.md`
  except `README.md`.
- In a guide or Finance Math, served content is everything outside an excluded section: the text under the title and every
  non-excluded section. In the user glossary it is the text of every entry outside an excluded section; the introduction and
  the section headings are not served text.
- The parsing of served content is a public function: for each served document, its non-excluded sections with heading, level,
  line range and lines. The H28 test and API.5b2's generator both use it.
- A test pins the set of strategy guides it finds to exactly one guide per `STRATEGIES` entry, using the existing `guide_name`
  rule in `scripts/generate_strategy_docs.py`, imported and not copied.
- Every failure message names the file, the line, the section heading and the reason.
- The H28 test and the pin test are in `tests/scripts/test_served_content.py`.

### H30 The Beginner Guide (2026-11-07)

- "How the project applies this model today" stops reading as a list of every strategy: it gives two or three strategies as
  explicitly illustrative examples, drops wording that implies the list is complete, and drops its links to the strategy index.
- "First steps after this guide" carries the exclude marker.
- "Further reading" stays served and keeps only links to served documents and external https links; a link to an unserved
  document is removed from the list, not excluded around.
- Elsewhere in the guide, a link to the strategy index is reworded as plain text or retargeted to a served guide.

### H31 The bundle's shape (2026-11-07)

For API.5b2.

- Terms are keyed by id. Each has a name, a definition (the short definition), a body (the rest of the entry) and a group.
- `groups` is an ordered list of `{id, title, terms}`, following the glossary's sections; the excluded command-line section is
  omitted.
- Documents are keyed by id. Each has a title, an introduction (the text under the title) and `sections`, an ordered flat list
  of `{id, heading, level, markdown}` covering every non-excluded heading at every level.
- A section id is its GitHub heading slug, computed over the whole file with excluded headings counted, so duplicate suffixes
  match GitHub's.
- Links are rewritten per [H14](#h14-links-in-the-bundle-2026-11-07).
- The file is written with sorted keys, a two-space indent and a final line feed.

### H32 A loader now (2026-11-07)

For API.5b2. Amends [H13](#h13-the-bundle-2026-11-07).

- The `help` package gains `load_help_bundle()`, which reads `help_bundle.json` through `importlib.resources` and validates it
  with the bundle model.
- `check_installed_package` checks that the installed bundle loads and holds every term id of the repository's bundle.
- API.6 keeps the endpoints.

### H33 Generator and drift (2026-11-07)

For API.5b2.

- `scripts/generate_help.py` mirrors `scripts/generate_openapi.py`: it writes, or with `--check` compares.
- It is a gate step in both wrappers and in CI after `generate_openapi --check`, and it has a drift test like
  `tests/scripts/test_generate_schemas.py`.
- It uses `check_help_content.py`'s served-content parser, and refuses to write while any leak check fails.
- Amendment ([H57](#h57-the-generator-runs-the-whole-checker-2026-11-07)): it runs the whole checker, not only the leak checks.

### H34 The contributor guide's guide edit site (2026-11-07)

- In `scripts/strategy_sites.toml`, the `guide` site's `why` says that the guide is served in the help bundle, that its
  explanatory sections are interface-neutral, that command-line material goes in excluded sections (whole sections, or a final
  "On the command line" subsection), and that `scripts/check_help_content.py` and the H28 test enforce it.
- The edit-site table in `docs/TOOL_DEVELOPMENT.md` is regenerated with `uv run python -m scripts.generate_strategy_docs`, not
  edited by hand.

### H35 Plan records (2026-11-07)

- This plan's sequence table has API.5b1 and API.5b2 rows in place of API.5b; API.5b1 is Complete, dated the day its pull
  request is opened, and API.5b2 is Planned.
- The API.5b section is split into "API.5b1 — The guides" and "API.5b2 — The bundle" with their branches, and an "API.5b1
  implementation record" is added in the style of the API.5a record.
- The contract has the same row and section split, with both branches, and each section's Detail points at this plan.
- "At a glance", "Where the history lives" and the acceptance criteria name API.5b1 and API.5b2.

### H36 Momentum's statuses and failures are served (2026-11-07)

- "Status, failures and exit codes" in the Momentum guide is renamed "Statuses and failures" and loses its exclude marker.
- The served section keeps the opening sentence; the status table without the exit-code column, with "the as-of boundary" in the
  third row; the reason and reason-code explanation, worded without `--json`; the rule that a provider failure never stores the
  provider's own error text, that the stored reason is a fixed message and that `provider_failure` names the provider and the
  kind of failure; and the fact that a saved run keeps a failed or unavailable outcome and that refreshing a watchlist records
  it as a run with that outcome instead of an error without a run.
- Everything else moves to a final "On the command line" subsection that carries the marker: the exit codes, the missing result
  part in `--json`, standard error, the provider check and `--no-provider-check`, `--save-run`, the exit code of a refresh that
  holds such a run, and the rejection of a wrong request before anything is fetched. Served text links neither the usage guide
  nor the workspace guide.

### H37 The served-document rules are documented now (2026-11-07)

- `docs/project/README.md` has a "Served documents" section after "Glossary entries": the served documents, interface-neutral
  sections, the exclude marker, the "On the command line" subsection, the leak rules and the command-name test, as a short list
  that links to [H24](#h24-served-sections-are-interface-neutral-2026-11-07),
  [H25](#h25-command-line-material-stays-in-its-guide-2026-11-07), [H27](#h27-the-leak-rules-2026-11-07) and
  [H28](#h28-command-names-in-code-spans-2026-11-07) and does not repeat their texts.
- Its documentation-only gate paragraph adds that a change to a served document must also pass
  `uv run pytest tests/scripts/test_served_content.py`.
- The "Noticed for later slices" item that left this wording to API.5b2 is removed.

### H38 No count in the Beginner Guide (2026-11-07)

- In "How the project applies this model today", "Three of the project's strategies, offered only as examples, ..." becomes "A few
  of the project's strategies, offered only as examples, ...".

### H39 The review basis (2026-11-07)

- The review relied on the pushed branch at commit 0bc90ff. These fixes are a follow-up commit on the same branch.

### H40 Plan records (2026-11-07)

- API.5b2 has no separate slice-plan document. This plan's H-records and its
  [implementation record](#33-api5b2-implementation-record) are its plan.
- "⚠ no slice plan yet" in this plan's API.5b2 section and in the contract's API.5b2 section is replaced by a link to this
  plan, and in this plan's own section by a link to the implementation record.
- API.5b2 is Complete in the sequence tables of this plan and of the contract, dated the day the pull request is opened, and
  API.6 is Next in the contract. A parent table changes only when a parent's status changes.
- "At a glance" and the acceptance criteria describe API.5b2.

### H41 Package layout (2026-11-07)

- A new layer-0 package `investment_analysis_engine/help/` whose `__init__.py` holds only a docstring.
- `investment_analysis_engine/help/bundle.py` defines the Pydantic models `HelpBundle`, `HelpTerm`, `HelpGroup`,
  `HelpDocument` and `HelpSection` and the function `load_help_bundle()`.
- The generated file is `investment_analysis_engine/help/help_bundle.json`.

### H42 Model and loader (2026-11-07)

- Every model is frozen with `extra="forbid"`.
- `load_help_bundle()` reads `help_bundle.json` through `importlib.resources`, validates it with `HelpBundle`, and is cached
  with `functools.cache`.
- A missing or invalid file raises as it is; there is no custom error type.

### H43 Integrity is checked by the model (2026-11-07)

A `HelpBundle` model validator requires:

- every term is in exactly one group, and its `group` names that group;
- every term id a group lists exists;
- every `help:` link in any term body, document introduction or section `markdown` resolves: `help:terms/<id>` to an
  existing term; `help:documents/<id>` to an existing document; `help:documents/<id>#<section-id>` to a section of that
  document.

A validation failure names the term, group, document or section and the bad id or link.

### H44 Group ids (2026-11-07)

- A group's id is the GitHub heading slug of the glossary's level-2 heading, computed with `slugify`, in the same way as
  section ids. It is not permanent.
- Nothing links to a group; `help:` links name only terms and documents.

### H45 Title and introduction (2026-11-07)

- A document's `title` is its level-1 heading text, and its `introduction` is the text under that heading.
- `sections` holds only headings of level 2 and below, in file order, excluded ones omitted. The level-1 heading is never a
  section.

### H46 Trimming (2026-11-07)

- Every term `body`, document `introduction` and section `markdown` has leading and trailing blank lines removed, and a
  trailing thematic break line (`---`, `***` or `___`, with any surrounding blank lines) removed. Ten glossary entries
  currently end in one.
- A term's `definition` is the entry's first paragraph (the short definition); its `body` is the entry's remaining text after
  that paragraph, or `""` when there is none.
- Exclude markers and `<a id>` lines never appear in bundle text.

### H47 Link rewriting (2026-11-07)

Only the link target changes; the link text is untouched. Relative targets are resolved from the source file's location.

| Source link | Bundle link |
| --- | --- |
| `GLOSSARY.md#<id>`, any relative form | `help:terms/<id>` |
| `#<id>` inside the glossary | `help:terms/<id>` |
| a served document, no anchor | `help:documents/<doc-id>` |
| a served document `#<slug>` | `help:documents/<doc-id>#<slug>` |
| a served document `#<its level-1 heading slug>` | `help:documents/<doc-id>` |
| `#<slug>` within the same document | as if it named its own file |
| absolute `https://` | unchanged |
| anything else | the generator refuses, naming the file, line and target |

Document ids are `beginner-guide`, `finance-math` and each strategy's alias. A strategy guide is matched to its alias with the
existing `guide_name` rule in `scripts/generate_strategy_docs.py`, imported, not copied.

### H48 Generator refusal (2026-11-07)

- `scripts/generate_help.py` mirrors `scripts/generate_openapi.py`: it writes the bundle, or with `--check` compares it.
- Both writing and `--check` first run `check_served_content`. If it reports any problem, the generator prints every problem
  and exits 1 without writing or comparing.
- The drift message names the command to run: `uv run python -m scripts.generate_help`.
- The generator builds the bundle through `HelpBundle`, so H43's checks apply before anything is written.
- Amendment ([H57](#h57-the-generator-runs-the-whole-checker-2026-11-07)): both modes first run `check_repository`, which
  includes the glossary entry rules, as well as `check_served_content`.

### H49 Installed-package check, amends H32 (2026-11-07)

- `check_installed_package` checks that the installed package's `load_help_bundle()` result equals the repository's bundle as
  a whole, not only its term ids.
- One subprocess in the installed environment prints the loaded bundle as JSON; the script compares it with the repository's
  `help_bundle.json` loaded through `HelpBundle`.
- `help/help_bundle.json` is in package-data.

### H50 Contributor gate and docs (2026-11-07)

- `docs/project/README.md` "Quality gates": a change to a served document must also pass
  `uv run python -m scripts.generate_help --check`, beside the existing `tests/scripts/test_served_content.py` requirement.
- `docs/project/README.md` "Served documents": after editing a served document, regenerate the bundle with
  `uv run python -m scripts.generate_help`; the gate fails on drift.
- `AGENTS.md` §7: one sentence after the documentation-only command list saying that a change to a served document must also
  pass the commands `docs/project/README.md`'s Quality gates section names for it, linking that section. No other `AGENTS.md`
  change.
- `scripts/strategy_sites.toml`: the `guide` site's `why` also says the help bundle is regenerated after a guide changes. The
  edit-site table in `docs/TOOL_DEVELOPMENT.md` is regenerated with the existing generator.

### H51 JSON text (2026-11-07)

- Sorted keys, two-space indent, a final line feed ([H31](#h31-the-bundles-shape-2026-11-07)), `ensure_ascii=False`, written
  as UTF-8 bytes. This is the same form as `schemas/openapi.json`.

### H52 Tests (2026-11-07)

- `tests/scripts/test_generate_help.py`: the drift test, in the style of `tests/scripts/test_generate_schemas.py`; a refusal
  case where a served-content problem stops writing; one case per row of H47's table; the H46 trimming cases.
- `tests/help/test_bundle.py`: each H43 rule failing and passing; the loader returning a validated bundle; a cached second
  call returning the same object.
- `tests/scripts/test_check_installed_package.py`: updated for H49.

### H53 Architecture (2026-11-07)

- `docs/project/ARCHITECTURE.md` §13 gains a `help` row at layer 0 with no imports. Its "Owns" cell reads: "The served help
  content: the generated help bundle, its model and its loader."
- Nothing imports `help` in this slice. API.6 adds the `api` import.

### H54 Stable references across locales (2026-11-07)

- Only term ids and document ids are stable references.
- Section ids and group ids are valid only within the bundle that carries them; a client follows them but never stores them.
- The contract's API.6 section carries this as a bullet, so the help endpoints and the GUI build on it.

### H55 Locale choice (2026-11-07)

A contract decision, implemented in API.6; the contract records it as
[A.5](API_CONTRACT_AND_SLICE_PLAN.md#a5-locale-choice-2026-11-07).

- Every endpoint that returns engine text honours `Accept-Language` and falls back to the engine's default locale. Every such
  response states the locale it used in `Content-Language`.
- The API serves a list of available locales, each with its name in its own language. A GUI builds its language picker from
  that list.
- Every piece of engine text the API serves follows the requested locale: help content, term names, labels, status and
  outcome wording, and error messages. W42's rule identifiers and arguments are what make translated error messages possible.
- Raw values stay language-neutral (JSON numbers, ISO dates); a client formats them.
- The list holds many locales by design, so it is not a single-value option.
- API.6 decides whether the list is its own endpoint or a field of an existing document, and whether the bundle has one file
  per locale.
- No locale field, argument or header handling is added in API.5b2.

### H56 One parser for served content (2026-11-07)

- `scripts/generate_help.py` carried copies of the checker's internals: its fence, heading, code-span and link patterns, and a
  function that reimplemented fence tracking, heading parsing, GitHub's duplicate-slug counting and exclude detection to find
  the glossary's level-2 headings. All of them are deleted.
- `scripts/check_help_content.py` makes the patterns the generator needs public (`FENCE_RE`, `HEADING_RE`, `CODE_SPAN_RE`,
  `LINK_RE`, `SCHEME_RE`) and uses them throughout. `ServedDocument` gains `groups`, a tuple of `ServedGroup` (heading, line,
  slug counted over every heading of the file, and whether the heading carries the exclude marker), filled for the user
  glossary and empty for every other document.
- The generator keeps only the thematic-break pattern, which the checker has no equivalent of. The checker's behaviour and
  messages are unchanged and the bundle regenerates byte for byte.

### H57 The generator runs the whole checker (2026-11-07)

Amends [H48](#h48-generator-refusal-2026-11-07).

- Both writing and `--check` first run `check_repository` (the glossary entry rules) and `check_served_content`. On any problem
  the generator prints every problem and exits 1 without writing or comparing.
- The generator's own refusals of an entry with no id line or no first paragraph are deleted.
- "A served document has exactly one level-1 heading" moves into the checker's structure rules for served documents, and the
  generator's own version is deleted.
- The refusal test covers an entry-rule problem and a document-structure problem as well as a served-content problem.

### H58 CI checks openapi.json for drift (2026-11-07)

- The CI `quality-and-test` job runs `uv run python -m scripts.generate_openapi --check` directly before the
  `generate_help --check` step, and `docs/project/README.md` lists it directly before the `generate_help` line, matching the
  wrappers' order.

### H59 Section level is constrained (2026-11-07)

- `HelpSection.level` is declared with `Field(ge=2, le=6)`, with a failing case (levels 1 and 7) and a passing case in
  `tests/help/test_bundle.py`.

### H60 The review basis (2026-11-07)

- The review relied on the pushed branch at commit 9a5e115. These fixes are a follow-up commit on the same branch.
