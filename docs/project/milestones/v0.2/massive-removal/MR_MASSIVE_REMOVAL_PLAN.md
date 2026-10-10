# MR — Massive Provider Removal: Plan

Removes the unfinished, untested Massive integration until a requirement makes it worth bringing back. This
document is the plan and the questions the project owner decides; nothing is removed by it. Placement among
other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this work does:** deletes the Massive adapter, its placeholder market client, its credential setting
  and every rule that exists only because Massive exists, then removes the documentation that tells a user to
  select it. SEC EDGAR stays the one security-fact provider and Yahoo the one quote provider.
- **What it is not:** a change to any formula, classification, result shape, strategy document or
  SEC EDGAR / Yahoo behavior. It does not add a provider abstraction, and it does not touch closed completion
  evidence.
- **Rules it follows:** stored data has no compatibility value in this period (`AGENTS.md` §0); the quality
  gate must not grow (see [§7](#7-tests-and-gate-time)); the managed gate with the 3.14 pass at the end of each
  slice; no dependency or `pyproject.toml` edit without explicit user permission (decision 9).
- **Where it sits:** after the common-header slice (SWC.4c.1, complete, #104, `6bf1c18`), before the Graham
  direct-versus-replay fix and before PH.2c, and before PKG so the package rename rewrites fewer files. No
  dependency on SWC.4d.
- **Verified against:** `main` at `6bf1c18` (2026-10-09), which already contains #104 (merged).
- **Decisions:** nine are open ([§3](#3-decisions)), each marked "needs a decision" with a recommendation. The
  recommendations are consistent with each other; the plan below describes them as the proposed scope.
- **Where the history lives:** why this exists is in [Background](#9-background-and-origin); the full inventory is
  in [Appendix A](#appendix-a-inventory).

### 1.1 Read this first

1. **Removal changes no behavior for SEC EDGAR or Yahoo users.** Every Massive branch is reached only when the
   security or quote provider is `massive`. The SEC and Yahoo adapters, the shared fetch helper, the resolver and
   the stored results do not read anything Massive owns. One construction side effect disappears: every
   `ProductionFinancialFactsProvider` builds a Massive adapter it never uses (`massive or MassiveFinancialFactsAdapter()`).
   The only user-visible change is for a user who selects Massive, who gets the existing unsupported-provider
   sentence, and a stray `MASSIVE_API_KEY` in the environment, which is ignored (not an error: only `IAN_`
   variables are validated).
2. **`ttm` is not a Massive-only value, so it cannot simply be deleted.** The rule says SEC EDGAR rejects `ttm`
   and only Massive accepts it, but the analyzer configs accept any injected provider identity and default every
   non-SEC identity to `ttm`. The evaluation tier (`fixture-synth`, cases GRN-02 and GRG-01) and dozens of
   resolver and analyzer tests run on that path, and twelve golden documents record a `ttm` basis. Removing
   the value outright would change evaluation and goldens and approach a classification change. Decision 2.
3. **The only secret setting goes with the key.** `massive_api_key` is the one `SecretStr` setting, so the
   "value is not shown" branch in `describe_validation_error` (`src/config.py`) and two tests that exist for it
   have no subject afterward. Decision 2 covers it.
4. **The `massive-api-client` dependency is declared and never imported.** Removing it edits `pyproject.toml` and
   `uv.lock`, which needs explicit permission (decision 9) and is why the plan proposes two slices.
5. **`MassiveClient` (the mock frame) is imported by nothing in production.** Only its package `__init__` and
   its tests reference it. It is dead code today.
6. **Not found:** the "Graham direct-versus-replay fix" is not recorded in any plan on `main`. The ordering
   above follows the project owner's instruction; the plan cannot link to it.

## 2. Sequence and status

Each slice ends with the complete managed quality gate including the 3.14 pass, and waits for explicit
project-owner authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| MR.1 | [Remove the provider, its rules and its documentation](#mr1--remove-the-provider-its-rules-and-its-documentation) | Planned | |
| MR.2 | [Remove the unused dependency](#mr2--remove-the-unused-dependency) | Planned | |

MR.1 starts only after this plan is approved and decisions 1 to 8 are answered. MR.2 starts only after MR.1
has merged and the project owner has granted the permission in decision 9. Both slices branch from `main`.

In the [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) the work package is row 13A, `Planned`, ahead
of PKG. It runs inside the Provider health package: after PH.2b (complete) and before PH.2c. The milestone table
orders rows by status, so the row sits after the two rows that are in progress; this plan states the real order.

## 3. Decisions

Every row needs a decision from the project owner. The full options and effects are in [§4](#4-the-questions-in-detail).

| # | Question | Recommendation | State |
| :--- | :--- | :--- | :--- |
| 1 | Do the `--data-provider` option and the provider fields stay with one accepted value each, or go? | Stay. `sec_edgar` and `yfinance` are the only accepted values, as FCF Growth already does. | Needs a decision |
| 2 | Does the `ttm` EPS basis go, with the Massive-only rules? | Delete the Massive rules and the `ttm` text in the CLI and stored selections; keep `ttm` in the analyzer configs, resolver and evidence vocabulary. Delete the secret-value branch with the key. | Needs a decision |
| 3 | Which stored versions bump? | None. The stored field names and types do not change; a row naming Massive is rejected as an unsupported value. | Needs a decision |
| 4 | Does anything still raise a provider failure with no kind? Can the completion test's exception go? | Only fixtures and one Yahoo guard still raise one; `provider_error` stays. The exception goes. Sentences in the PH documents change as listed in [§6.2](#62-edits-to-the-provider-health-documents). | Needs a decision |
| 5 | What does removal take out of PH.2c and Step 3.5? | Nothing from PH.2c's scope; nothing in the Step 3.5 contract assumes Massive. | Needs a decision |
| 6 | Where does the note for bringing it back live? | One entry in `EVIDENCE_PROVIDER_ROADMAP.md`, with the last commit, what was unfinished, and the requirement that would justify it. | Needs a decision |
| 7 | Size and gate time. | Accept: net test count and gate time do not grow; the numbers are in [§7](#7-tests-and-gate-time). | Needs a decision |
| 8 | One slice or two? Work-package code and position. | Two slices: MR.1, then MR.2. Code `MR`, row 13A of the milestone table. | Needs a decision |
| 9 | Permission to remove `massive-api-client` from `pyproject.toml` and `uv.lock`. | Grant it for MR.2. | Needs a decision |

## 4. The questions in detail

### 4.1 Provider options (decision 1)

After removal the security provider has one valid value and the quote provider one. The `--data-provider` option
exists on `graham-number`, `graham-growth`, `fcf-growth` and `watchlist add-selection`. There is no quote-provider
option: the quote provider is a field of the stored selection and the analyzer config, resolved from the security
provider.

| Option | What it does | Stored versions | Bringing a provider back |
| :--- | :--- | :--- | :--- |
| **A. Keep, one value (recommended)** | `CLI_SECURITY_PROVIDERS = ("sec_edgar",)`, `CLI_QUOTE_PROVIDERS = ("yfinance",)`; the option and the fields stay; the "supported providers" sentences name one. | No change: field names and types are the same. | Add one value to a tuple, one branch in `cli_composition`, one registration. |
| B. Keep the fields, drop the option | Removes `--data-provider` from four commands and the watchlist flags. | No change. | Re-add the option, its help and its tests as well. |
| C. Remove option and fields | Removes the fields from both Graham selections and configs. | Both Graham `config_schema_version` values bump to 2, with about twelve test files, two goldens and two schemas following. | Re-add the fields and bump again. |

Why A: FCF Growth already declares `provider_id: Literal["sec_edgar"]` behind the same option, so A makes the
three SEC-backed commands consistent. C is not a removal of Massive: the evaluation tier builds the Graham
configs with a fixture provider identity, so removing the fields rewrites evaluation composition.

### 4.2 The `ttm` basis and the Massive-only rules (decision 2)

What is Massive-only, by strategy:

- **Graham Number:** `ttm` is accepted only with Massive (`is_massive_provider` and `MASSIVE_ONLY_EPS_BASIS`
  rule in `GrahamNumberConfig.validate_method`), and Massive requires `bvps_override`. SEC EDGAR accepts
  `three_year_average` only.
- **Graham Growth:** the same `ttm`-only rule; no book-value rule. SEC EDGAR accepts `three_year_average` and
  `fiscal_year`. Checked: nothing else in Growth is Massive-specific.
- **Shared:** `eps_basis.py` (`MASSIVE_ONLY_EPS_BASIS`, `is_massive_provider`, a docstring), the CLI help text
  of both commands and the matching expected-output files.

What is **not** Massive-only: `ttm` as an injected provider's default (`default_eps_basis_for_provider` returns it
for every non-SEC identity), the `GrahamNumberEPSBasis` and `GrahamGrowthEPSBasis` literals, the calculation
check in `graham_number/calculation.py`, the resolver's single-observation basis, `FinancialBasis` and
`PeriodKind` `TTM`, the `period_kind` check constraint, the display labels, the evaluation cases and fixtures,
and the Step 3.5 inputs document, which relies on `PeriodKind.TTM`.

| Option | Effect |
| :--- | :--- |
| A. Remove the Massive rules only | Smallest change. The stored selection and the CLI still list `ttm`, which no valid selection can hold (SEC EDGAR already rejects it). The generated watchlist schema keeps advertising it. |
| **B. Remove Massive rules; narrow the stored selection and CLI (recommended)** | The selection and CLI accept only values SEC EDGAR accepts (Number: `three_year_average`; Growth: `three_year_average`, `fiscal_year`). The analyzer configs, resolver, evaluation and evidence keep `ttm`. Two generated schemas change. |
| C. Remove `ttm` everywhere | Rewrites evaluation cases GRN-02 and GRG-01, the fixture provider, dozens of tests and twelve goldens; touches classification. Not recommended. |

Other things left unreachable once Massive is gone, and what to do with each:

- The non-SEC branches of `default_eps_basis_for_provider` and of the quote-provider default are reachable only
  through injected identities (evaluation and tests). **Keep**; correct their docstrings.
- `ProductionFinancialFactsProvider`'s `massive` argument and mapping entry, `build_massive_production_provider`,
  the "Massive access is not configured" error and `PROVIDER_DISPLAY_NAMES["massive"]` (unknown identifiers fall
  back to the raw text). **Delete.**
- The `SecretStr` branch of `describe_validation_error`, its wording "(its value is not shown)" and the tests
  `test_invalid_secret_value_is_never_echoed` and `test_bad_secret_is_reported_without_echoing_the_value`.
  **Recommend delete**; a future credential brings the branch back with its own test. Alternative: keep it as a
  latent branch, at the cost of untested-by-construction code.
- `"src.data.massive"` in the layering test's cycle-package set. **Delete.**

### 4.3 Stored data (decision 3)

| Version field | Where | Bumps? | Why |
| :--- | :--- | :--- | :--- |
| `config_schema_version` (Graham Number 1, Graham Growth 1) | the selection in watchlist entries and in the stored run | **No** (yes under option C) | Field names and types are unchanged; only the accepted set narrows. Bump it if the project owner prefers the "saved by an earlier version" sentence, at the cost of invalidating every stored Graham selection and run and touching about twelve more test files. |
| `run_schema_version`, `projection_version` | the stored run | No | Envelope unchanged. |
| `result_schema_version`, `evidence_codec_version` | each strategy | No | Result and evidence shapes are unchanged; provider identities in provenance are free text. |
| Strategy document `schema_version` | the four documents | No | The four strategy schemas carry no provider or basis enumeration; `ttm` in `fcf-growth.schema.json` is the period-kind vocabulary and stays. |
| Resolved-input and market-data cache rows | database | No | Rows naming `massive` are inert: no key will match them. |

Effects, confirmed against the code: a stored selection or run is rejected only if it names `massive` as the
security or the quote provider (a `sec_edgar` selection with a Massive quote provider is allowed today), or names
`ttm` under option B. Nothing else stops decoding. Where it is rejected:

- **Watchlist entry:** `parse_stored_selection` in `src/workspace/watchlists.py` raises `StoredSelectionError`
  with the one sentence "its stored selection is not in a shape this version can read". The watchlist commands
  report it and exit 1.
- **Stored run:** `SQLiteAnalysisRunRepository._decode` validates the envelope, whose `selection` is the closed
  selection union; the error is pydantic's `ValueError`, so `runs show` fails with `invalid_stored_run` and
  pydantic's multi-line text, not a one-sentence message. `runs list` reads only indexed summary columns and still
  lists the run. This message quality is not changed by MR.

### 4.4 Provider-failure work (decision 4)

After removal, kindless provider failures still have producers, none of them a real service call:

- `src/data/yfinance/financial_facts.py` raises `FinancialProviderError` with no kind when its injected clock
  returns a naive datetime. This is a defect-class guard, not a provider fact.
- The evaluation fixtures raise `FinancialProviderError` or `DataFetchError` with no kind to simulate a failure
  (`fixtures/graham.py`, `fixtures/fcf_earnings_growth.py`, `fixtures/market_data.py`).
- Test doubles.

The Massive placeholder `DataFetchError` raises (the empty mock range and the unimplemented quote) also carried no
kind and fall away with the package. So `provider_error` stays in the public vocabulary and still has producers
(fixtures, the Yahoo guard, any future unclassified adapter). **Recommendation:** leave `yfinance/financial_facts.py`
alone here; whether that guard should be a kind-bearing failure or a plain defect belongs with PH.2c's undecided
list.

The completion test (`tests/data/test_provider_adapter_handlers.py`) has exactly one allowed broad handler,
`MassiveClient.fetch_data`; with the package gone the set `_RETAINED` is empty and the test asserts no
broad handler in any scanned module. The `massive` glob and the `massive/client.py` entry in the coverage
assertion go. The exception can go. The sentences in the PH documents that change are in
[§6.2](#62-edits-to-the-provider-health-documents).

### 4.5 PH.2c and Step 3.5 (decision 5)

- **PH.2c:** nothing in its decisions, scope, output changes or inventory names Massive. The carriers (resolver,
  FCF input resolver, instrument profile, security identity) are provider-neutral. What changes for it: a
  stored `provider_failure.inputs[].provider_id` can no longer be `massive`, and two existing tests that use
  `"massive"` as an arbitrary provider identity are moved to a neutral value by MR.1.
- **Step 3.5:** the contract states fundamentals come from SEC EDGAR only because no other configured provider
  can serve a historical `as_of`; no sentence assumes Massive. The slice-inputs document relies on
  `PeriodKind.TTM`, which MR keeps. After MR the provider tuples are one-element tuples, ready for a second
  provider without further change.

### 4.6 Bringing it back (decision 6)

A future reader needs three facts, kept in one short entry in `EVIDENCE_PROVIDER_ROADMAP.md` (the candidate
backlog, where "when a requirement makes it worthwhile" is recorded) rather than a document of its own:

- **Last commit that contains it:** the parent of the MR.1 merge on `main`. At the time of this plan that is
  `6bf1c18`; MR.1 records the final value. A git tag is an alternative, but a tag is outward-facing and needs
  its own approval, so the plan proposes the commit hash.
- **What was unfinished and untested:** it supplied only current TTM diluted EPS and the latest trade price; no
  book value, annual EPS, AAA yield or historical `as_of`; it was never run against the live service (no paid
  key), so its tests use canned JSON only; the market client was a mock frame with an unimplemented quote;
  there was no health check; Graham Number through it needed a manual book-value override; the
  `massive-api-client` dependency was declared and never used.
- **A requirement that would justify it:** proposed for the project owner to edit: a strategy that needs a
  field SEC EDGAR and Yahoo cannot supply; a quote source that Yahoo's unofficial endpoint cannot be relied on
  for; or the roadmap's multi-provider reconciliation, which needs a second source.

The roadmap's two other sentences that name Massive (multi-provider reconciliation; "data on hand") change too
([§6.1](#61-source-settings-and-documentation)).

### 4.7 Size and gate time (decision 7)

Counts are in [§7](#7-tests-and-gate-time) and [Appendix A](#appendix-a-inventory); the gate time is measured
there. The commitment: no new slow test, and a net reduction in tests.

### 4.8 Slicing, code and position (decision 8)

**Two slices, MR.1 and MR.2.** MR.1 holds everything that can be done without touching dependencies: it is one
concern (a provider leaves) and one reviewable diff that is mostly deletion, and it keeps the gate offline
(`uv run --no-sync`). MR.2 is `pyproject.toml` and `uv.lock` only; it needs explicit permission, and
regenerating the lock may need the network and may drop transitive packages, which deserves its own review.
Splitting MR.1 further (selection layer, then adapter) would leave a half-removed state that the documentation and the gate
cannot describe truthfully. If decision 9 is granted in advance and the lock regenerates offline, the project owner may
fold MR.2 into MR.1.

The code is `MR` ("Massive Removal"); `R4` is avoided for the reason PKG gives. Position: after SWC.4c.1 and PH.2b,
before the Graham direct-versus-replay fix, PH.2c and PKG; the milestone row is 13A, `Planned` (numbered so no later row renumbers).

## 5. The work

### MR.1 — Remove the provider, its rules and its documentation

- **Problem:** an unfinished integration that cannot be tested (it needs a paid key) sits in production
  composition, the settings, two strategies' validation, the CLI help and eleven user documents, and every new
  strategy would copy its patterns.
- **Decision:** remove it entirely, keep the provider fields and options with one accepted value, keep `ttm` in
  the analyzer vocabulary, bump no stored version (decisions 1 to 3, as recommended).
- **Scope:** the areas in [§6](#6-scope-by-area); the files are in [Appendix A](#appendix-a-inventory).
- **Branch:** `feat/mr-1-remove-massive`, from `main`.
- **Detail:** this document.

### MR.2 — Remove the unused dependency

- **Problem:** `massive-api-client` is declared in `pyproject.toml` and imported nowhere.
- **Decision:** remove it and regenerate `uv.lock` (decision 9).
- **Scope:** `pyproject.toml` and `uv.lock` only.
- **Branch:** `chore/mr-2-remove-dependency`, from `main` after MR.1 has merged.
- **Detail:** this document.

## 6. Scope by area

### 6.1 Source, settings and documentation

| Area | Change |
| :--- | :--- |
| Adapter package | Delete `src/data/massive/` (four files: facts adapter, placeholder market client, constants, package init). |
| Registration and composition | `src/data/financial/providers.py`, `production.py`: drop the Massive import, export and constructor argument. `src/cli_composition.py`: drop `build_massive_production_provider` and its branch; the unsupported-provider sentence names `sec_edgar` only. |
| Settings | `src/config.py`: drop `massive_api_key`, its validator and the docstring mention; drop the `SecretStr` branch (decision 2). No example or environment file is tracked. |
| Selections and configs | `src/workspace/selection_base.py` (tuples), `src/workspace/requests.py` (docstring), `graham_number` and `graham_growth` `config.py`, `selection.py`, `cli.py` (Massive rules, sentences and help text); under option B, a selection-only EPS-basis literal per strategy. `eps_basis.py`: drop the Massive helper and constant, correct the docstring. |
| Presentation | `src/reporting/presentation.py`: drop the display name. Schemas: regenerate the two watchlist schemas (option B). |
| User documents | Eleven documents ([Appendix A](#a4-documentation)): remove the Massive sections, commands and anchors; the doc-link check enforces the anchors. `SMOKE_TESTING.md` loses one step, so its command count changes. |
| Project documents | `ARCHITECTURE.md`, `DISCOVERY_WORKBOOK.md` (present-state lines only), `EVIDENCE_PROVIDER_ROADMAP.md` (two sentences and the new entry), `PROVIDER_DEBUGGING.md` (one sentence). |

### 6.2 Edits to the provider-health documents

Not edited by this plan. MR.1 makes these edits and no others. Completed slices keep their delivered text.

| Document | Where | Change |
| :--- | :--- | :--- |
| `PH2_HANDLER_INVENTORY.md` | §3 "Massive" heading and both rows | Replace the section with one sentence saying Massive was removed by MR.1 and naming the plan. The heading stays so the existing `#3-massive` link keeps working. |
| `PH2_HANDLER_INVENTORY.md` | §7 first sentence, "in sections 1 to 3" | "in sections 1 and 2". |
| `PH2_HANDLER_INVENTORY.md` | §7, "fails on any handler other than the retained `MassiveClient.fetch_data` mock" and "except the one retained mock" | The test fails on any such handler; no handler is retained. |
| `PH_CONTRACT_AND_SLICE_PLAN.md` | Scope limits: "Checks for Massive until its adapter has a live endpoint, and for the local Ollama service" | "Checks for any provider other than Yahoo and SEC EDGAR, and for the local Ollama service". |
| `PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md` | §1, At a glance | One added sentence: Massive was removed by MR.1 after PH.2a and PH.2b delivered; the Massive text in §4 and §8 records what was delivered. |
| `PROVIDER_DEBUGGING.md` | the sentence "Massive is not checked: its adapter has no live endpoint." | Delete the sentence. |

Left unchanged as completion evidence or closed slice text: `PH1_LIVE_SUITE_SLICE_PLAN.md` (its Massive sentence
and the `#3-massive` link remain true and valid), and the PH.2a text of `PH_CONTRACT_AND_SLICE_PLAN.md` (the
"Decision" and "Scope" bullets naming the Massive facts adapter) and `PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md`
(§1, §4 and §8 Massive sentences).

## 7. Tests and gate time

- **Removed:** 28 test functions: all of `test_massive_cli_configuration.py` (2), `test_massive_client.py` (4),
  `test_massive_failure_kinds.py` (5) and `test_cli_graham_slice_f_routing.py` (2); eight in
  `test_production_providers.py`; two in `test_graham_growth_default_policy.py`; three in
  `test_settings_environment.py`; and one each in `test_startup_settings_errors.py` and `test_display_labels.py`.
  Their parametrized cases go with them.
- **Edited:** 21 test files (names in [Appendix A](#a3-tests)), by replacing `massive` as an example value with the
  remaining provider or a neutral identity, narrowing parametrizations, and renaming the completion test.
- **Added:** no new test function. One assertion is added to an existing settings test: a stray
  `MASSIVE_API_KEY` in the environment is ignored. One rejection case with the literal `massive` stays in
  `test_requests.py` as the regression for the retired provider; it replaces a deleted case.
- **Verification:** the strategy-document and direct-command goldens have zero diff; only the two help-text
  files (and under option B the two schemas) change. The test count and the gate time are recorded at
  MR.1's completion and must not exceed the figures below.
- **Gate time, measured on `main` at `6bf1c18` with this plan's two documents added:** the managed wrapper with
  `--extra-python 3.14` took 657 s end to end (pytest 309 s on 3.12 and 315 s on 3.14; 4,518 passed, 6 skipped,
  2 deselected; coverage 93%). The Massive tests that can be selected by name or parameter (40 cases) run in about
  3 s, of which 1.2 s is the two start-up subprocess cases. Removal therefore saves about 3 s per pass, around 1% of
  the gate; the commitment is that the gate does not grow, not that it shrinks noticeably.
- **Local gate for MR.1 and MR.2:** the managed wrapper with `--extra-python 3.14`.

## 8. Scope limits and acceptance criteria

- No change to a formula, classification, result shape, strategy document or stored version (unless the project
  owner overrides decision 3).
- No source, test, schema or expected-output change in the planning pull request.
- A case-insensitive search for `massive` over `src/`, `tests/` and `docs/user/` returns nothing except the retired-provider rejection case
  and the roadmap note; over `docs/project/` it returns only completion evidence, closed slice text, the
  roadmap entry and this plan.
- The strategy-document and direct-command goldens are unchanged; `ian health` is unchanged.
- The mypy, Ruff, document-link and sequence-table checks pass, and the managed gate passes on 3.12 and 3.14.
- MR.1 records the last commit that contains Massive in the roadmap entry.

## 9. Background and origin

The Massive market client was added with the Step 2.3 Graham work (2026-08-25) and the facts adapter with the
Step 2.4 work (2026-08-30), to give the Graham methods a second data route. It has never run against the live
service, because it needs a paid key: the existing-analysis correctness evidence lists it as not reached, and the
Provider health work package (PH.1) left it unchecked for the same reason. The project owner decided to remove it for the time being and to bring it back,
or reimplement it, when a requirement makes it worthwhile. The quality gate is already long, so the removal must
not add to it.

## Appendix A. Inventory

Each item is delete, edit, or leave as history. The symbol is the stable reference; the line is for convenience
at `6bf1c18`. **Overlap with #104:** #104 has merged (it is `6bf1c18`). Of the files it changed, these are in this
inventory: `src/strategies/graham_number/cli.py`, `src/strategies/graham_growth/cli.py`, `docs/user/USAGE.md`,
`docs/user/SMOKE_TESTING.md` and `PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md`. The Graham envelopes, presenters,
codecs and `src/strategy_wiring.py` that #104 changed contain no Massive reference and are not edited here.

### A.1 Delete

| File | Symbols |
| :--- | :--- |
| `src/data/massive/__init__.py` | package exports `MassiveClient`, `MASSIVE_PROVIDER_ID` |
| `src/data/massive/client.py` | `MassiveClient` (`fetch_data` mock frame, line 38; `fetch_current_price`, line 55) |
| `src/data/massive/constants.py` | `MASSIVE_PROVIDER_ID` |
| `src/data/massive/financial_facts.py` | `MassiveFinancialFactsAdapter` (`is_configured`, `fetch_facts`), `MASSIVE_TTM_EPS_FIELD`, `MASSIVE_LAST_TRADE_FIELD`, private helpers |
| `tests/data/test_massive_client.py` | 4 tests |
| `tests/data/test_massive_cli_configuration.py` | 2 tests |
| `tests/data/test_massive_failure_kinds.py` | 5 tests |
| `tests/test_cli_graham_slice_f_routing.py` | 2 tests |

### A.2 Edit: source and configuration

| File | Symbol | Change |
| :--- | :--- | :--- |
| `src/data/financial/providers.py` | imports (4–5), `__all__` (10, 13) | Drop Massive. |
| `src/data/financial/production.py` | imports (16–17), `ProductionFinancialFactsProvider.__init__` (40, 46) | Drop the `massive` argument and map entry. |
| `src/cli_composition.py` | module docstring (3), imports (32, 34), `build_massive_production_provider` (57), `build_graham_resolver` (80–87), `__all__` (112) | Drop Massive; sentence names `sec_edgar`. |
| `src/config.py` | class docstring (119), `massive_api_key` (141), `reject_whitespace_in_api_key` (222), `describe_validation_error` secret branch (326) | Drop. |
| `src/data/financial/eps_basis.py` | `_MASSIVE_PROVIDER_ID` (6), `MASSIVE_ONLY_EPS_BASIS` (8), `default_eps_basis_for_provider` docstring (14), `is_massive_provider` (22) | Drop the Massive items; correct the docstring. |
| `src/strategies/graham_number/config.py` | imports (10, 12), `validate_method` (59–60, 68–69) | Drop the `ttm`-only and book-value rules. |
| `src/strategies/graham_growth/config.py` | imports (10, 12), `validate_method` (67–68) | Drop the `ttm`-only rule. |
| `src/strategies/graham_number/selection.py` | `_restrict_security_provider` (50), `_restrict_quote_provider` (65), `_resolve_configuration` docstring (88) | One-value sentences. |
| `src/strategies/graham_growth/selection.py` | same validators (51, 66) | One-value sentences. |
| `src/strategies/graham_number/cli.py` | `--eps-basis` help (120–122) | Drop "with Massive". |
| `src/strategies/graham_growth/cli.py` | `--eps-basis` help (127–129) | Drop "with Massive". |
| `src/workspace/selection_base.py` | `CLI_SECURITY_PROVIDERS`, `CLI_QUOTE_PROVIDERS` (10–11), comment (6) | One-element tuples. |
| `src/workspace/requests.py` | module docstring (14–16) | Name SEC EDGAR only. |
| `src/reporting/presentation.py` | `PROVIDER_DISPLAY_NAMES` (62) | Drop `"massive"`. |
| `pyproject.toml`, `uv.lock` | `massive-api-client` (27) | MR.2 only; needs permission. |

### A.3 Tests

Edit (21 files). Test functions are named where a function changes.

| File | Change |
| :--- | :--- |
| `tests/analysis/graham_value/test_analyzer_config.py` | `test_provider_basis_matrix`: drop the `massive` row. |
| `tests/analysis/graham_value/test_production_providers.py` | Delete the seven `test_massive_*` tests and `test_graham_number_assembly_can_use_sec_eps_and_massive_quote`; edit `test_production_provider_routes_without_rewriting_provider_identity`. |
| `tests/data/repositories/test_watchlist_repository.py` | Two tests use a Massive selection as "a second configuration"; use a different override. |
| `tests/data/test_production_quote_routing.py` | Drop the Massive recording provider. |
| `tests/data/test_provider_adapter_handlers.py` | Drop the glob, the expected `massive/client.py` entry and `_RETAINED`; rename the retained-handler test. |
| `tests/data/test_provider_failure.py`, `tests/data/test_transport_failure_kinds.py` | Use a neutral provider identity. |
| `tests/expected_output/cli_help/graham-number.txt`, `graham-growth.txt` | Regenerate (help text). |
| `tests/reporting/test_display_labels.py` | Delete `test_provider_display_name_massive`; edit the mappings test. |
| `tests/test_cli.py` | Three tests that use Massive as an example value. |
| `tests/test_cli_fcf_earnings_growth.py`, `tests/test_cli_health.py` | Use a neutral unsupported identity. |
| `tests/test_cli_save_run.py` | Docstring mention. |
| `tests/test_cli_workspace.py` | One selection example. |
| `tests/test_graham_growth_default_policy.py` | Delete two Massive tests; edit the `ttm` rejection test. |
| `tests/test_settings_environment.py` | Delete three tests; edit the case-variant test and the cleanup set; add the stray-key assertion. |
| `tests/test_startup_settings_errors.py` | Delete the secret test. |
| `tests/test_strategy_import_layering.py` | Drop `src.data.massive` from the cycle set. |
| `tests/workspace/test_requests.py` | Seven tests: narrow parametrizations; keep one `massive` rejection case. |
| `tests/workspace/test_runs.py` | One selection example. |

Possible further edits found only by running the suite: `tests/test_cli_graham_commands.py` (its `--eps-basis ttm`
case under option B). Test fakes that use `ttm` through an injected provider (dozens of tests) are unchanged.

### A.4 Documentation

Edit, user documents (11): `BEGINNER_GUIDE.md`, `FINANCE_MATH.md`, `GLOSSARY.md` (remove the Massive entry),
`INSTALLATION.md` (remove the section, the troubleshooting entry and the credential sentence),
`QUICKSTART.md`, `README.md`, `SMOKE_TESTING.md`, `USAGE.md`, `WORKSPACE.md`, `strategies/GRAHAM_GROWTH.md`,
`strategies/GRAHAM_NUMBER.md`.

Edit, project documents (4 plus 3 PH documents in [§6.2](#62-edits-to-the-provider-health-documents)):
`ARCHITECTURE.md` (lines 233, 236, 563), `DISCOVERY_WORKBOOK.md` (lines 262, 284, 356, 361; the decision row at
776 stays as history), `EVIDENCE_PROVIDER_ROADMAP.md` (lines 86, 118, and the new entry), `PROVIDER_DEBUGGING.md`.

### A.5 Left as history

Twenty-three documents are left unchanged because they record what was decided or delivered when Massive existed:
`integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md`, `IR7_ARCHITECTURE_DOC_CONTRIBUTOR_PASS.md`;
`existing-strategy-correctness/` `ESC_A_DEFECT_LEDGER.md`, `ESC_D_RENEWAL_PLAN.md`, `ESC_E1_COMPARISON_EVIDENCE.md`,
`ESC_E2_GRAHAM_NUMBER_EVIDENCE.md`, `ESC_E3_GRAHAM_GROWTH_EVIDENCE.md`, `ESC_E5_FCF_EVIDENCE.md`,
`ESC_E_FINAL_ACCEPTANCE.md`, `ESC_E_RENEWAL_PLAN.md`; `provider-health/PH1_LIVE_SUITE_SLICE_PLAN.md`;
`r1/R1_CONTRACT_AND_SLICE_PLAN.md`; `step-2.3/` `STEP_2_3_GRAHAM_DESIGN.md`, `STEP_2_3_GRAHAM_SLICE_PLAN.md`;
`step-3.3/STEP_3_3_CONTRACT_AND_SLICE_PLAN.md`; `step-3.4/` `SLICE_B1_CLINE_HANDOFF.md`,
`SLICE_C2_COMPLETION_EVIDENCE.md`, `SLICE_F3_G1_COMPLETION_EVIDENCE.md`, `SLICE_G3_H_COMPLETION_EVIDENCE.md`,
`SLICE_I1_COMPLETION_EVIDENCE.md`, `SLICE_I3_COMPLETION_EVIDENCE.md`, `STEP_3_4_CONTRACT_AND_SLICE_PLAN.md`;
`swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md`. Logs, `htmlcov/`, the egg-info and `.pytest_cache` also mention
Massive; they are ignored build or run output and are not edited.

### A.6 Kept deliberately (not Massive-specific)

`ttm` in `GrahamNumberEPSBasis`, `GrahamGrowthEPSBasis` (analyzer configs), `graham_number/calculation.py`,
`analysis/shared/financial_resolution.py`, `FinancialBasis.TTM`, `PeriodKind.TTM`, the `period_kind` check
constraint in `data/repositories/schema.py`, the evidence and valuation display labels, the evaluation cases
and fixtures (`evaluation/cases/graham_*.py`, `evaluation/fixtures/graham.py`), the `ttm` entry in the glossary,
and the `period_kind` vocabulary in `schemas/fcf-growth.schema.json`.
