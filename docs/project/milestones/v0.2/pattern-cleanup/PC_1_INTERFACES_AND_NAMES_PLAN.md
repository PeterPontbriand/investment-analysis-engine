# PC.1 — Interfaces and Names: Slice Plan

Removes the single-valued `--data-provider` option and its chain
([#143](https://github.com/PeterPontbriand/investment-analysis-engine/issues/143)), and renames "sentence" to
"message" for user-facing failure text
([#140](https://github.com/PeterPontbriand/investment-analysis-engine/issues/140)). It also records, and does not
implement, the decision on [#111](https://github.com/PeterPontbriand/investment-analysis-engine/issues/111).

Parent plan: [PC contract and slice plan](PC_CONTRACT_AND_SLICE_PLAN.md#pc1--interfaces-and-names).

## 1. At a glance

- **What this slice does:** removes an option, two stored fields per strategy and the code behind them, because each can
  hold only one value (`AGENTS.md` §9); and replaces the word "sentence" with "message" wherever it names user-facing
  failure text.
- **What it is not:** a formula, classification or calculation change; an implementation of #111 (that is
  [PC.4](PC_CONTRACT_AND_SLICE_PLAN.md#pc4--one-shared-mapping-from-statuses-to-a-run-outcome)); a change to any
  `provider_id` that records which source supplied a fact.
- **Rules it follows:** a consolidation package under `AGENTS.md` §0. Stored selection shapes change without migration
  or compatibility code, and `CONFIG_SCHEMA_VERSION` is bumped for each. The complete managed gate runs on the final
  commit.
- **Decisions:** all approved by the project owner on 2026-10-19 ([A.1](#a1-approved-decisions-2026-10-19)).

## 2. Sequence and status

| Unit | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| Slice plan | [This document](#3-the-work-units) and the parent-plan updates | Complete | 2026-10-19 |
| #143 | [Remove the data-provider option and its chain](#143--remove-the-data-provider-option-and-its-chain) | Complete | 2026-10-20 |
| #140 | [Rename "sentence" to "message"](#140--sentence-becomes-message) | Next | |
| Completion | [Plan rows and the final gate](#completion) | Planned | |

## 3. The work units

### Decision record for #111

- **Problem:** each strategy writes its own function from statuses to a run outcome.
- **Decision:** yes, one shared mapping. PC.1 records the decision and implements none of it; it is slice PC.4, planned
  after PC.3. The design is in the
  [PC.4 section of the parent plan](PC_CONTRACT_AND_SLICE_PLAN.md#pc4--one-shared-mapping-from-statuses-to-a-run-outcome).
- **Scope:** documentation only: the parent plan, and Appendix A.9 and the pre-3.5.0 decision list of the Step 3.5
  contract.
- **Branch:** `refactor/pc-1-interfaces-and-names`.
- **Detail:** [PC contract and slice plan](PC_CONTRACT_AND_SLICE_PLAN.md#pc4--one-shared-mapping-from-statuses-to-a-run-outcome); ⚠ no slice plan yet for PC.4.

### #143 — remove the data-provider option and its chain

- **Problem:** `--data-provider` accepts only `sec_edgar`. Behind it sit stored fields that can hold only one value:
  `security_provider_id` and `quote_provider_id` on the Graham configs, selections and tool dependencies, and
  `provider_id` on the FCF Growth config, selection and tool dependencies.
- **Decision:** remove the option and the whole strategy-owned chain. Each strategy uses its fixed provider as a named
  constant (`SEC_PROVIDER_ID`, and the existing yfinance provider constant for quotes). Remove the "Known exception,
  tracked in issue #143" sentence from `AGENTS.md` §9.
- **Scope:** the edit sites below, their tests, the user docs and the help snapshots. Stored shapes change under
  `AGENTS.md` §0, with no migration.
- **Branch:** `refactor/pc-1-interfaces-and-names`.
- **Detail:** the sections below.

#### Edit sites (removed)

| Site | Removal |
| :--- | :--- |
| `investment_analysis_engine/cli_support.py` | `_canonical_provider_id`; the `security_provider_id` → `--data-provider` entry of the option-name map |
| `investment_analysis_engine/analysis/selection_base.py` | `CLI_SECURITY_PROVIDERS`, `CLI_QUOTE_PROVIDERS` |
| `investment_analysis_engine/strategies/graham_number/` and `graham_growth/` | `security_provider_id` and `quote_provider_id` on config, selection and tool dependencies; the `--data-provider` option of each `cli.py`; the dead `else self.security_provider_id` branch in both configs; the `run_*_analysis` service and the execution parameters that only carried them |
| `investment_analysis_engine/strategies/fcf_growth/` | `provider_id` on config, selection (`Literal["sec_edgar"]`) and tool dependencies; the `--data-provider` option of `cli.py` |
| `investment_analysis_engine/cli_workspace.py`, `cli_watchlist_flags.py`, `cli_composition.py` | the `--data-provider` option of `watchlist create` and `watchlist add-selection`, the `data_provider` flag field and the `data_provider` parameter of `build_graham_resolver` |
| `investment_analysis_engine/evaluation/fixtures/graham.py`, `investment_analysis_engine/strategies/_graham/evaluation.py` and the two Graham `evaluation.py` modules | the evaluation tier ran both Graham strategies against the fixture provider `fixture-synth`, which the removed fields carried. The fixture's company facts and precedence cache now carry `SEC_PROVIDER_ID` and its quote carries `YFINANCE_PROVIDER_ID` (as FCF Growth's evaluation composition already relabels its facts), `PROVIDER_ID` is removed, and `GrahamFixtureInputs` loses its `provider_id` field. The AAA fact carries `SEC_PROVIDER_ID` too, because the strategy always supplies the AAA yield as an override and `MACRO_ID` is unchanged. Field identifiers and values stay synthetic |
| `AGENTS.md` §9 | the "Known exception, tracked in issue #143" sentence |
| `schemas/` | regenerated: `watchlist.schema.json` and `watchlist-delete.schema.json` lose the removed selection fields. The watchlist document is unversioned, so no `schema_version` changes; each selection's own `config_schema_version` is bumped |
| `scripts/` and `scripts/strategy_templates/` | any generator or conformance reference to the removed fields (found while implementing) |

#### Kept

- The `provider_id` parameters of shared resolvers and other shared code that more than one provider uses.
- The `security_provider_id` and `quote_provider_id` parameters of the resolvers' `assemble_*` methods: a resolver is
  built over any provider the caller injects, and its tests inject others.
- The `provider_id` provenance fields of evidence, documents and published schemas: they record which source supplied
  a fact and take more than one value.

#### Stored shapes

- `CONFIG_SCHEMA_VERSION` is bumped in the `vocabulary.py` of Graham Number, Graham Growth and FCF Growth.
- There is no migration or compatibility code. How an existing selection of the old shape is now rejected is found by
  running it and is reported with the slice.

#### Tests removed

Tests whose only subject was the removed behavior: `test_cli_graham_unsupported_provider_is_an_invalid_parameter_before_network_setup`,
`test_graham_quote_provider_routing_is_method_aware`, `test_cli_fcf_growth_rejects_unapproved_provider_without_network_work`,
`test_number_quote_provider_default`, `test_dependency_classes_reject_blank_provider_ids`,
`test_graham_number_uses_the_foreign_private_issuer_provider_and_identity` and
`test_graham_growth_uses_the_foreign_private_issuer_identity`; the `SUP-5` rows and the provider rows of the
parity and order tables in `test_command_validation_failures.py`; and the `_canonical_provider_id` assertions of
`test_cli_support.py`. `test_unsupported_providers_rejected` becomes `test_removed_provider_fields_are_rejected`,
which asserts that a stored selection naming a removed field is refused.

#### Documents and snapshots

`docs/user/USAGE.md` (every `--data-provider` mention, including the `invalid_parameter` paragraph's list of options),
`docs/user/strategies/FCF_GROWTH.md`, `docs/user/strategies/GRAHAM_NUMBER.md`, any other user or generated strategy
document that names the option, `docs/user/WORKSPACE.md` where it shows the removed fields, the help snapshots under
`tests/expected_output/cli_help/` and the stored-selection snapshots under `tests/expected_output/workspace_commands/`.

### #140 — "sentence" becomes "message"

- **Problem:** user-facing failure text is called a "sentence" in names, docs and tests; the project's word is
  "message".
- **Decision:** a failure text is a "message", optionally prefixed by its field ("reason message"). "Sentence" stays
  only where actual sentences are counted. Where text promises that a message is one sentence it reads "a
  one-sentence message".
- **Scope:** `investment_analysis_engine/`, `scripts/`, `tests/`, `schemas/`, `docs/`, `AGENTS.md` and `README.md`,
  excluding `docs/project/milestones/` (a historical record). Identifiers are renamed, including
  `provider_failure_sentence`, `_PROVIDER_FAILURE_SENTENCES`, `_UNCLASSIFIED_PROVIDER_FAILURE_SENTENCE`,
  `_MEMORY_TARGET_SENTENCE` and test names.
- **Branch:** `refactor/pc-1-interfaces-and-names`.
- **Detail:** the inventory and rules below.

#### Rules

| Rule | Action | Meaning |
| :--- | :--- | :--- |
| N1 | rename | "sentence" is part of an identifier, parameter, variable or test name |
| N2 | rename | "sentence" names user-facing failure text in prose, a docstring, a comment or a field description |
| N3 | rename | text promises that a message is one sentence: write "a one-sentence message" |
| K1 | keep | the text counts actual sentences, such as "The message is one sentence" in `core/settings_error.py` |
| K2 | keep | the hits in `MASTER_PLAN.md` and `DISCOVERY_WORKBOOK.md` that describe sentences of plain-English answers |

A line rewritten under N3 still contains "one-sentence", so it passes the guard test through the allowlist.

#### Schemas

Three schema files change only in field descriptions: failure, provider-health and database-maintenance-report. The
Pydantic `Field` descriptions change and `uv run python scripts/generate_schemas.py` regenerates them. No
`schema_version` is bumped, because no shape changes.

#### Refreshed inventory (2026-10-19)

192 hits. The issue's inventory predates the package rename. The Text column is an excerpt around the hit.

| File | Line | Text | Action | Rule |
| :--- | ---: | :--- | :--- | :--- |
| scripts/generate_strategy_docs.py | 163 | """Return the sentence that says why ''block'' is missing its markers or d… | rename | N2 |
| scripts/generate_strategy_docs.py | 175 | """Return one sentence per generated block that differs from its regenerat… | rename | N3 |
| investment_analysis_engine/cli_database.py | 37 | _MEMORY_TARGET_SENTENCE = "Database maintenance requires a file-backed targ… | rename | N1 |
| investment_analysis_engine/cli_database.py | 85 | …asonCode.CONFIGURATION_ERROR, _MEMORY_TARGET_SENTENCE), | rename | N1 |
| scripts/generate_schemas.py | 57 | """Return one sentence per schema file that is missing or differs from the… | rename | N3 |
| schemas/provider-health.schema.json | 16 | "description": "The failure detail, a sentence for people that is not stable; null when the check … | rename | N2 |
| schemas/provider-health.schema.json | 36 | "description": "What the check requests; a sentence for people, not stable.", | rename | N2 |
| investment_analysis_engine/cli_support.py | 51 | # One sentence per kind of provider failure, then one for a failur… | rename | N3 |
| investment_analysis_engine/cli_support.py | 53 | _PROVIDER_FAILURE_SENTENCES = { | rename | N1 |
| investment_analysis_engine/cli_support.py | 61 | _UNCLASSIFIED_PROVIDER_FAILURE_SENTENCE = ( | rename | N1 |
| investment_analysis_engine/cli_support.py | 66 | def provider_failure_sentence(error: DataFetchError / FinancialProviderError, tic… | rename | N1 |
| investment_analysis_engine/cli_support.py | 67 | """Return the sentence for a provider failure, from its kind, the provider… | rename | N2 |
| investment_analysis_engine/cli_support.py | 70 | return _UNCLASSIFIED_PROVIDER_FAILURE_SENTENCE.format(subject=subject) | rename | N1 |
| investment_analysis_engine/cli_support.py | 71 | return _PROVIDER_FAILURE_SENTENCES(error.kind).format(subject=subject, provider=error… | rename | N1 |
| investment_analysis_engine/cli_support.py | 120 | :func:'provider_failure_sentence'; the codes in ''_SHOWN_AS_RAISED'' and every ''dat… | rename | N1 |
| investment_analysis_engine/cli_support.py | 139 | message = provider_failure_sentence(exception, ticker) | rename | N1 |
| investment_analysis_engine/cli_support.py | 365 | … failure envelope to standard output, or its sentence to standard error, and exit 1.""" | rename | N2 |
| investment_analysis_engine/cli_support.py | 377 | …ry command that has no analysis to name: the sentence on standard error, or with | rename | N2 |
| investment_analysis_engine/cli_workspace.py | 132 | keeps its own sentence; any other exception is an ''execution_error'' with… | rename | N3 |
| investment_analysis_engine/cli_workspace.py | 159 | …or, as the direct commands do; otherwise the sentence goes to standard error. | rename | N2 |
| schemas/failure.schema.json | 197 | …''reason'' and\n''diagnostics().reason'' are sentences for people and carry no guarantee.", | rename | N2 |
| docs/user/WORKSPACE.md | 202 | …nd exits '1'; without '--json' it prints the sentence on standard error. | rename | N2 |
| schemas/database-maintenance-report.schema.json | 41 | …e from ''reason'' to ''reason_code'' and the sentence from\n''message'' to ''reason''. A reader of versio… | rename | N2 |
| schemas/database-maintenance-report.schema.json | 85 | "description": "A sentence for people; not stable.", | rename | N2 |
| docs/user/USAGE.md | 218 | …l result, a stable 'reason_code', a 'reason' sentence and sanitized diagnostics; the process exits with c… | rename | N3 |
| docs/user/USAGE.md | 312 | …checked'. Branch on 'verdict'; the lines are sentences for people. | rename | N2 |
| docs/user/USAGE.md | 337 | … an 'invalid_parameter' failure (exit 1, the sentence on standard error, or with '--json' the failure doc… | rename | N2 |
| docs/user/USAGE.md | 342 | …gured' or 'failed'; 'probe' and 'detail' are sentences for people. | rename | N2 |
| docs/user/DATABASE.md | 63 | (a sentence for people); unavailable fields are null. Version 1… | rename | N2 |
| docs/user/DATABASE.md | 64 | 'reason' and the sentence 'message', so a reader written for version 1 must c… | rename | N2 |
| docs/user/DATABASE.md | 65 | …chema_version' first: 'reason' now holds the sentence. The report shares the failure | rename | N2 |
| docs/user/DATABASE.md | 167 | sentence. The envelope reports the condition and never upgra… | rename | N2 |
| investment_analysis_engine/config/__init__.py | 333 | """Describe the first invalid setting as one sentence that names the environment variable. | rename | N3 |
| investment_analysis_engine/config/__init__.py | 342 | A single sentence naming the variable and what was wrong with its val… | rename | N3 |
| investment_analysis_engine/core/settings_error.py | 7 | The message is one sentence that names the offending variable or variables, so … | keep | K1 |
| investment_analysis_engine/core/settings_error.py | 15 | The message is one sentence that names the file relative to the project root an… | keep | K1 |
| docs/project/PROVIDER_DEBUGGING.md | 62 | … 'not_configured'). 'probe' and 'detail' are sentences for people and may change. 'detail' is | rename | N2 |
| docs/project/PROVIDER_DEBUGGING.md | 244 | is down. The sentence of a command such as 'ian momentum' says only that … | rename | N2 |
| docs/project/PROVIDER_DEBUGGING.md | 280 | sentence is logged with its traceback, and an exception that… | rename | N2 |
| docs/user/INSTALLATION.md | 160 | …ing 'ian --help') the application prints one sentence naming the variable to the error stream and exits w… | rename | N3 |
| docs/project/MASTER_PLAN.md | 15 | … and gets an answer in ordinary words. Every sentence points to stored evidence, and every number is plac… | keep | K2 |
| docs/project/MASTER_PLAN.md | 90 | 3. Write        a local model writes sentences; each names its evidence, | keep | K2 |
| docs/project/MASTER_PLAN.md | 93 | 4. Check        each sentence is tested against its evidence; | keep | K2 |
| docs/project/MASTER_PLAN.md | 94 | │       a sentence that fails is removed | keep | K2 |
| docs/project/MASTER_PLAN.md | 99 | …estion, read a named part of a filing, write sentences, and check sentences. It never calculates, never t… | keep | K2 |
| docs/project/MASTER_PLAN.md | 103 | …estion, read a named part of a filing, write sentences, and check them. Rules, not the model, then decide… | keep | K2 |
| docs/project/MASTER_PLAN.md | 117 | …te only what stored evidence supports. Every sentence names its evidence, every number is placed by the e… | keep | K2 |
| docs/project/MASTER_PLAN.md | 178 | …ites answers, which reads filings and checks sentences, the accuracy bars each must meet, and how many fi… | keep | K2 |
| docs/project/MASTER_PLAN.md | 234 | …nd questions, read filing passages and check sentences well enough. / | keep | K2 |
| docs/project/MASTER_PLAN.md | 238 | / **ASK.2 — Answer check** / Every sentence is tested against its evidence before it is shown; … | keep | K2 |
| docs/project/MASTER_PLAN.md | 243 | …-English questions is answered so that every sentence traces to stored evidence, no number was typed by a… | keep | K2 |
| docs/project/MASTER_PLAN.md | 292 | / **Plain-English Answers** / Sentences in an answer that trace to stored evidence / All, … | keep | K2 |
| docs/project/MASTER_PLAN.md | 295 | / **Plain-English Answers** / Sentence checking / Catches at least 9 in 10 planted errors;… | keep | K2 |
| docs/project/MASTER_PLAN.md | 311 | …ays more than the evidence does** / A fluent sentence misstates a result, and the reader trusts it / The … | keep | K2 |
| docs/project/MASTER_PLAN.md | 312 | …er is taken as advice** / A reader acts on a sentence as if it were a recommendation / Advice requests ar… | keep | K2 |
| docs/project/MASTER_PLAN.md | 344 | …n, its research plan, the evidence used, the sentences shown and the check results. An answer is not a re… | keep | K2 |
| docs/project/MASTER_PLAN.md | 363 | … rendering reduces a failure to one friendly sentence: | keep | K2 |
| scripts/strategy_conformance.py | 760 | """Return one sentence per descriptor whose checked-in schema exists but d… | rename | N3 |
| investment_analysis_engine/main.py | 8 | …ere, before any other project import, as one sentence and no traceback. | rename | N3 |
| investment_analysis_engine/main.py | 9 | …e same settings, so it is not up yet and the sentence is not logged. | rename | N2 |
| docs/project/DISCOVERY_WORKBOOK.md | 75 | … named parts of filings, and write and check sentences. Nothing else. | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 82 | …n gets a plain-English answer in which every sentence traces to stored evidence and no number was typed b… | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 144 | - Every sentence in an answer traces to stored evidence. | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 181 | …*Write an answer** (v0.3) / Typed evidence / Sentences that name their evidence and leave slots for numbe… | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 182 | / **Check an answer** (v0.3) / One sentence and its evidence / *Supported*, *not supported* or … | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 212 | …no structure: SEC filings, and its own draft sentences. | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 214 | …ears on the question, and checking a written sentence against the result it cites. Selecting, gating and … | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 242 | …n answer's sources are its explanation: each sentence lists the evidence it rests on. | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 373 | …n, its research plan, the evidence used, the sentences shown, and the check results. Written once; showin… | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 401 | - correct sentences and copies with a planted error. | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 480 | If a model is unavailable or too many sentences fail the check, the user gets the ordinary result … | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 654 | …t, given that a small local model writes the sentences? | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 656 | …ready-computed results, beyond relevance and sentence checking, that still passes the test in §7? | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 687 | - **Answer check** — Test of each written sentence against the evidence it names, by rules first and a… | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 688 | …n, its research plan, the evidence used, the sentences shown and the check results. | keep | K2 |
| docs/project/DISCOVERY_WORKBOOK.md | 799 | …computed results is limited to relevance and sentence checking; revisit when the ledger has scored entrie… | keep | K2 |
| tests/test_cli_failure_envelope.py | 4 | sentence to standard error and nothing to standard output. E… | rename | N2 |
| tests/test_cli_failure_envelope.py | 76 | @pytest.mark.parametrize(("flags", "sentence"), _MOMENTUM_WINDOW_CASES) | rename | N2 |
| tests/test_cli_failure_envelope.py | 77 | …invalid_parameter_envelope(flags: list(str), sentence: str) -) None: | rename | N1 |
| tests/test_cli_failure_envelope.py | 85 | assert envelope("reason") == sentence | rename | N1 |
| tests/test_cli_failure_envelope.py | 88 | …n flags if item.startswith("--") and item in sentence) | rename | N1 |
| tests/test_cli_failure_envelope.py | 91 | @pytest.mark.parametrize(("flags", "sentence"), _MOMENTUM_WINDOW_CASES) | rename | N2 |
| tests/test_cli_failure_envelope.py | 92 | …_momentum_window_failure_in_text_mode_is_the_sentence_on_standard_error( | rename | N1 |
| tests/test_cli_failure_envelope.py | 93 | flags: list(str), sentence: str | rename | N1 |
| tests/test_cli_failure_envelope.py | 99 | …ssert normalize_cli_output(result.stderr) == sentence | rename | N1 |
| tests/test_cli_failure_envelope.py | 102 | @pytest.mark.parametrize(("flags", "sentence"), _MOMENTUM_WINDOW_CASES) | rename | N2 |
| tests/test_cli_failure_envelope.py | 103 | …me_momentum_window_failure(flags: list(str), sentence: str) -) None: | rename | N1 |
| tests/test_cli_failure_envelope.py | 111 | …ssert normalize_cli_output(result.stderr) == sentence | rename | N1 |
| tests/test_cli_failure_envelope.py | 164 | def test_workspace_text_failures_keep_the_sentence_on_standard_error(arguments: list(str)) -) None: | rename | N1 |
| tests/test_cli_failure_envelope.py | 314 | …refreshing_an_empty_watchlist_in_text_is_the_sentence_on_standard_error() -) None: | rename | N1 |
| tests/test_cli.py | 372 | ("kind", "sentence"), | rename | N2 |
| tests/test_cli.py | 385 | …k_run: MagicMock, kind: ProviderFailureKind, sentence: str | rename | N1 |
| tests/test_cli.py | 391 | …p() == f"{_YAHOO_NOT_CHECKED_SWITCHED_OFF}\n{sentence}" | rename | N2 |
| tests/test_cli.py | 397 | assert document("reason") == sentence | rename | N1 |
| tests/test_cli.py | 788 | sentence = ( | rename | N1 |
| tests/test_cli.py | 797 | assert text.stderr.strip() == sentence | rename | N1 |
| tests/test_cli.py | 800 | assert document("reason") == sentence | rename | N1 |
| tests/test_cli.py | 899 | sentence = "Unable to analyze FCIM: yfinance did not serve t… | rename | N1 |
| tests/test_cli.py | 901 | …p() == f"{_YAHOO_NOT_CHECKED_SWITCHED_OFF}\n{sentence}" | rename | N2 |
| tests/test_cli.py | 903 | assert document("reason") == sentence | rename | N1 |
| tests/test_cli.py | 908 | … a per-ticker fault into an empty frame; the sentence stays factual.""" | rename | N2 |
| tests/test_cli.py | 913 | sentence = "Unable to analyze FCIM: yfinance returned no dat… | rename | N1 |
| tests/test_cli.py | 915 | …p() == f"{_YAHOO_NOT_CHECKED_SWITCHED_OFF}\n{sentence}" | rename | N2 |
| tests/test_cli.py | 917 | assert document("reason") == sentence | rename | N1 |
| investment_analysis_engine/data/provider_failure.py | 73 | message: The sentence the raised failure starts with; the exception text … | rename | N2 |
| tests/_workspace_command_output.py | 11 | …. Nothing else is altered, so a changed key, sentence or exit code shows in the stored files. | rename | N2 |
| investment_analysis_engine/utils/README.md | 37 | …hat a command handler reports with a generic sentence is logged with its traceback by 'execution_errors'.… | rename | N2 |
| investment_analysis_engine/strategies/momentum/cli.py | 50 | ''invalid_parameter'' failure with the same sentence, which names the offending option. The option | rename | N1 |
| tests/workspace_documents/test_analysis_run_replay.py | 368 | …alized to the live command's investor-facing sentence... | rename | N2 |
| tests/workspace_documents/test_analysis_run_replay.py | 379 | …ng; replay must render the normalized public sentence, not this text. | rename | N1 |
| tests/workspace_documents/test_analysis_run_replay.py | 401 | …ct_run_normalizes_raw_quote_reason_to_public_sentence() -) None: | rename | N1 |
| tests/workspace_documents/test_analysis_run_replay.py | 402 | """Replay renders the investor-facing quote sentence and never leaks the raw technical reason.""" | rename | N2 |
| tests/workspace_documents/test_analysis_run_replay.py | 413 | …ason must be replaced by the investor-facing sentence... | rename | N2 |
| tests/workspace_documents/test_analysis_run_replay.py | 723 | …ct_run_normalizes_raw_quote_reason_to_public_sentence() -) None: | rename | N1 |
| investment_analysis_engine/reporting/failure_envelope.py | 29 | ''reason'' is the sentence to show; the caller sanitizes it. Only a failed his… | rename | N2 |
| tests/test_settings_environment.py | 131 | sentence = describe_validation_error(raised.value, os.enviro… | rename | N1 |
| tests/test_settings_environment.py | 133 | assert sentence.startswith("Environment variable ") | rename | N1 |
| tests/test_settings_environment.py | 134 | assert "DATABASE_BUSY_TIMEOUT_MS" in sentence.upper() | rename | N1 |
| tests/test_settings_environment.py | 135 | assert "not-a-number" not in sentence | rename | N1 |
| tests/test_documented_conventions.py | 3 | …ined to one function. Each test fails with a sentence that | rename | N2 |
| tests/reporting/test_failure_envelope.py | 274 | """The report's stable code and sentence are named as the envelope's are.""" | rename | N2 |
| tests/reporting/test_failure_envelope.py | 375 | …velope(classify_failure(error).reason_code, "sentence", cause=error) | rename | N2 |
| tests/test_command_validation_failures.py | 4 | sentence to standard error and nothing to standard output; a… | rename | N2 |
| tests/test_command_validation_failures.py | 43 | sentence: str | rename | N1 |
| tests/test_command_validation_failures.py | 59 | row: str, arguments: tuple(str, ...), sentence: str, parameters: tuple(str, ...), *, json_flag: bo… | rename | N1 |
| tests/test_command_validation_failures.py | 61 | return Check(row, arguments, sentence, parameters, json_flag) | rename | N1 |
| tests/test_command_validation_failures.py | 218 | provider_sentence = ( | rename | N1 |
| tests/test_command_validation_failures.py | 226 | provider_sentence, | rename | N1 |
| tests/test_command_validation_failures.py | 364 | for row, options, sentence, parameters in windows: | rename | N1 |
| tests/test_command_validation_failures.py | 365 | …d(_check(row, _direct("momentum", *options), sentence, parameters, json_flag=True)) | rename | N1 |
| tests/test_command_validation_failures.py | 370 | sentence, | rename | N1 |
| tests/test_command_validation_failures.py | 379 | sentence, | rename | N1 |
| tests/test_command_validation_failures.py | 391 | for row, options, sentence in fcf: | rename | N2 |
| tests/test_command_validation_failures.py | 392 | …_check(row, _direct("fcf-growth", *options), sentence, (options(0),), json_flag=True)) | rename | N1 |
| tests/test_command_validation_failures.py | 397 | sentence, | rename | N1 |
| tests/test_command_validation_failures.py | 665 | def _assert_sentence(check: Check, reason: str) -) None: | rename | N1 |
| tests/test_command_validation_failures.py | 667 | assert reason.startswith(check.sentence), reason | rename | N1 |
| tests/test_command_validation_failures.py | 669 | assert reason == check.sentence | rename | N1 |
| tests/test_command_validation_failures.py | 673 | …name in reason, f"{name} is missing from the sentence" | rename | N2 |
| tests/test_command_validation_failures.py | 677 | def test_the_sentence_goes_to_standard_error_and_the_command_exits_1(chec… | rename | N1 |
| tests/test_command_validation_failures.py | 683 | _assert_sentence(check, document("reason")) | rename | N1 |
| tests/test_command_validation_failures.py | 686 | _assert_sentence(check, result.stderr.strip()) | rename | N1 |
| tests/test_command_validation_failures.py | 690 | def test_the_unknown_alias_sentence_names_every_declared_alias(alias: str) -) None: | rename | N1 |
| tests/test_command_validation_failures.py | 691 | …alias is among the choices the unknown-alias sentence offers.""" | rename | N2 |
| tests/test_command_validation_failures.py | 713 | _assert_sentence(check, document("reason")) | rename | N1 |
| investment_analysis_engine/reporting/documents/health.py | 45 | …ield(description="What the check requests; a sentence for people, not stable.") | rename | N2 |
| investment_analysis_engine/reporting/documents/health.py | 48 | description="The failure detail, a sentence for people that is not stable; null when the check … | rename | N2 |
| tests/test_startup_settings_errors.py | 1 | …ne environment is reported at startup as one sentence on stderr, with exit code 2.""" | rename | N3 |
| tests/test_startup_settings_errors.py | 38 | def _assert_one_sentence_failure(run: subprocess.CompletedProcess(str), *nam… | rename | N3 |
| tests/test_startup_settings_errors.py | 51 | _assert_one_sentence_failure(run, "IAN_NO_SUCH_SETTING", "matches no eng… | rename | N3 |
| tests/test_startup_settings_errors.py | 61 | _assert_one_sentence_failure(run, "IAN_DATA_DIR", "ian_data_dir", "diffe… | rename | N3 |
| tests/test_startup_settings_errors.py | 64 | def test_help_reports_the_same_sentence_as_a_command_for_a_bad_variable() -) None: | rename | N1 |
| tests/test_startup_settings_errors.py | 74 | _assert_one_sentence_failure(run, "IAN_DATABASE_BUSY_TIMEOUT_MS", "valid… | rename | N3 |
| tests/test_startup_settings_errors.py | 81 | _assert_one_sentence_failure(run, "valid integer") | rename | N3 |
| tests/test_startup_settings_errors.py | 89 | _assert_one_sentence_failure(run, name, "must be an absolute path") | rename | N3 |
| tests/test_startup_settings_errors.py | 96 | _assert_one_sentence_failure(run, "IAN_DATABASE_URL", "must be an absolu… | rename | N3 |
| tests/test_startup_settings_errors.py | 104 | _assert_one_sentence_failure(run, "IAN_CONFIG_DIR", "cannot be set there… | rename | N3 |
| tests/test_cli_support.py | 19 | provider_failure_sentence, | rename | N1 |
| tests/test_cli_support.py | 110 | _KIND_SENTENCES = ( | rename | N1 |
| tests/test_cli_support.py | 122 | @pytest.mark.parametrize(("kind", "sentence"), _KIND_SENTENCES) | rename | N1 |
| tests/test_cli_support.py | 123 | def test_the_sentence_table_names_the_provider_and_ticker_per_kind( | rename | N1 |
| tests/test_cli_support.py | 124 | …alProviderError), kind: ProviderFailureKind, sentence: str | rename | N1 |
| tests/test_cli_support.py | 126 | assert provider_failure_sentence(exception_type("private", kind=kind, provider_id="s… | rename | N1 |
| tests/test_cli_support.py | 129 | def test_the_sentence_table_has_one_row_per_kind_and_one_for_an_unclassif… | rename | N1 |
| tests/test_cli_support.py | 130 | sentences = { | rename | N2 |
| tests/test_cli_support.py | 131 | provider_failure_sentence(DataFetchError("x", kind=kind, provider_id="p"), "T… | rename | N1 |
| tests/test_cli_support.py | 133 | assert len(sentences) == len(ProviderFailureKind) | rename | N2 |
| tests/test_cli_support.py | 134 | assert provider_failure_sentence(DataFetchError("private detail"), None) == ( | rename | N1 |
| tests/test_cli_support.py | 140 | @pytest.mark.parametrize(("kind", "sentence"), _KIND_SENTENCES) | rename | N1 |
| tests/test_cli_support.py | 142 | …alProviderError), kind: ProviderFailureKind, sentence: str | rename | N1 |
| tests/test_cli_support.py | 155 | assert document("reason") == sentence | rename | N1 |
| investment_analysis_engine/reporting/documents/failure.py | 50 | ''diagnostics().reason'' are sentences for people and carry no guarantee. | rename | N2 |
| tests/test_cli_workspace.py | 573 | def _unreadable_run_sentence(run_id: UUID) -) str: | rename | N1 |
| tests/test_cli_workspace.py | 580 | …rts_an_envelope_that_fails_validation_in_one_sentence( | rename | N3 |
| tests/test_cli_workspace.py | 596 | sentence = _unreadable_run_sentence(run.analysis_run_id) | rename | N1 |
| tests/test_cli_workspace.py | 604 | assert text.stderr.strip() == sentence | rename | N1 |
| tests/test_cli_workspace.py | 606 | …ocument("reason")) == ("invalid_stored_run", sentence) | rename | N1 |
| tests/test_cli_workspace.py | 639 | …cli_output(result.output) == _unreadable_run_sentence(run.analysis_run_id) | rename | N1 |
| tests/test_cli_workspace.py | 644 | _unreadable_run_sentence(run.analysis_run_id), | rename | N1 |
| tests/test_cli_workspace.py | 843 | …lary the help text and the error read as the sentence documents.""" | rename | N2 |
| tests/test_cli_workspace.py | 1171 | …code_is_an_unexpected_failure_with_one_fixed_sentence( | rename | N1 |
| tests/test_cli_workspace.py | 1176 | sentence = f"{typed} failed unexpectedly." | rename | N1 |
| tests/test_cli_workspace.py | 1184 | assert text.stderr.strip() == sentence | rename | N1 |
| tests/test_cli_workspace.py | 1190 | …, document("reason")) == ("execution_error", sentence) | rename | N1 |
| tests/test_cli_workspace.py | 1198 | …ion_that_declares_its_own_code_keeps_its_own_sentence() -) None: | rename | N1 |
| tests/test_cli_workspace.py | 1202 | side_effect=WatchlistNotFoundError("own sentence"), | rename | N2 |
| tests/test_cli_workspace.py | 1207 | …t("reason")) == ("watchlist_not_found", "own sentence") | rename | N2 |
| investment_analysis_engine/reporting/documents/database.py | 6 | sentence (''reason''), and its codes are drawn from the same… | rename | N2 |
| investment_analysis_engine/reporting/documents/database.py | 20 | …e from ''reason'' to ''reason_code'' and the sentence from | rename | N2 |
| investment_analysis_engine/reporting/documents/database.py | 22 | sentence, so check ''schema_version'' first. | rename | N1 |
| investment_analysis_engine/reporting/documents/database.py | 34 | reason: str = Field(description="A sentence for people; not stable.") | rename | N2 |
| tests/utils/test_operational_logging.py | 144 | …ef test_an_unexpected_error_reports_the_same_sentence_and_logs_its_cause_and_traceback(tmp_path: Path) -)… | rename | N1 |

### The three guard tests

All three are in `tests/test_documented_conventions.py`.

| Test | Asserts |
| :--- | :--- |
| `test_data_provider_option_is_rejected_with_exit_2` | parametrized over `CLI_STRATEGIES` and the two watchlist commands: `--data-provider` exits 2 |
| `test_no_strategy_model_has_a_provider_id_field` | no selection, config or tool-dependency model of any strategy has a field whose name ends in `provider_id` |
| `test_the_word_sentence_appears_only_in_allowlisted_phrases` | a word scan over the #140 roots fails on "sentence" unless the line holds a phrase of a short explicit tuple (for example "one sentence", "one-sentence"); the failure message names the file, the line number and the rule |

The two #111 guard tests belong to PC.4.

### Completion

- In the parent plan, PC.1 is set to Complete with the date and PC.2 to Next.
- In the milestone plan, row `14B` goes from Next to In progress.
- The complete managed gate runs on the final commit, with the extra interpreter.

## 4. Scope limits

- No formula, classification or calculation result changes.
- No change to a provenance or evidence `provider_id`, or to shared code that more than one provider uses. If a removal
  reaches either, the work stops for the project owner.
- No implementation of #111.
- Nothing under `docs/project/milestones/` is renamed.

## 5. Acceptance criteria

- `--data-provider` is rejected with exit 2 by every command that had it, and the help screens do not show it.
- No selection, config or tool-dependency model has a field whose name ends in `provider_id`.
- The word scan finds no "sentence" outside the allowlist.
- The three schema files differ from their previous text only in descriptions, and the watchlist schemas differ only
  by the removed selection fields.
- The complete managed gate passes.

## 6. Background: origin of this slice

PC removes patterns that Step 3.5 strategies would copy. PC.1 takes the two that need the project owner's decision on a
public interface or name: a single-valued option, and a word the project no longer uses for failure text. See
[PC §6](PC_CONTRACT_AND_SLICE_PLAN.md#6-background-origin-of-this-work-package).

## Appendix A: Decision records

### A.1 Approved decisions (2026-10-19)

Decisions of the project owner, 2026-10-19.

- **#111:** yes; slice PC.4, planned after PC.3. The function, the removals and the guard tests are in the parent plan.
- **#143:** remove the option and the whole strategy-owned chain, and also `quote_provider_id`, a stored field that can
  hold only `yfinance`. Keep the `provider_id` parameters of shared code and the provenance fields. Bump the three
  `CONFIG_SCHEMA_VERSION` values, with no migration.
- **#140:** the rule, reach, keep list, one-sentence wording, identifier renames, schema handling and guard test above.
