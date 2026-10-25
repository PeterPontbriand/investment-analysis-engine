# Step 3.5 slice 3.5.0 — Momentum result status and the side-by-side refresh table: Slice Plan

The slice plan for [slice 3.5.0](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#350--side-by-side-refresh-table) of Step 3.5. It
covers two sub-slices, written against `main` at `618bc1d`.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this plan does:** gives Momentum the result-level status every other strategy already has (3.5.0a), then
  builds the side-by-side table over one refresh and its command, `ian runs compare <refresh-id>` (3.5.0b).
- **Why in this order:** the table needs a status and a reason on every cell of every strategy. Momentum is the one
  strategy with none, and it raises on a provider failure instead of storing a result, so a refresh loses the job
  instead of showing it. The table is built on a Momentum that already behaves like the other three.
- **What it is not:** a formula or classification change, a new strategy, a new data mapping, a ranking, or a new
  persistence form. Momentum's numbers are unchanged. Full list: [Scope limits](#4-scope-limits).
- **Rules both sub-slices follow:**
  - The consolidation rules of `AGENTS.md` §0 applied to 3.5.0a: stored data had no compatibility value, so version
    fields were bumped and no migration code was written. The first commit of 3.5.0b removed §0 and made its two
    lasting rules permanent in §4 ([E1 and E2](#a1-decisions-d1-to-d11-2026-10-25)): a change to a persisted shape
    bumps its version field, and runs stored under an older version stay in the database and are refused by version
    when read; and an open item is never the outcome of a design decision.
  - The managed quality gate after every sub-slice, and explicit authorization before the next begins.
  - No new `CalculationStatus`, `ReasonCode` or `FailureReasonCode` member.
- **Where the detail lives:** the file inventories, the test lists and the documentation changes are in
  [Appendix B](#appendix-b-file-inventories-tests-and-documentation); decision records are in
  [Appendix A](#appendix-a-decision-records).

## 2. Sequence and status

Each sub-slice ends with the managed quality gate and is gated by explicit authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 3.5.0a | [Momentum result-level status](#350a--momentum-result-level-status) | Complete | 2026-10-25 |
| 3.5.0b | [Side-by-side refresh table](#350b--side-by-side-refresh-table) | Complete | 2026-10-25 |

3.5.0a is implemented on the branch that carries this plan and merges as one pull request. 3.5.0b starts from `main`
after that pull request merges.

## 3. The sub-slices

### 3.5.0a — Momentum result-level status

- **Problem:** Momentum is the only strategy whose result has no `execution_status`. Its native status is `None`, so
  its run always completes. A provider failure, a failed data-quality check or an empty history raises, and a raise
  stores nothing: `refresh_watchlist` records the job as an `error` with no run (`workspace/refresh.py`, `_failed`),
  so a refresh over Momentum cannot show, replay or compare the failure. A ticker with too little history for the
  long average stores a completed run whose trend is `UNKNOWN`, which is a missing input reported as success.
- **Decision (D2, D3, D4):**
  - `MomentumRun` gains `execution_status`, a `CalculationStatus`, as `FCFEarningsGrowthResult` has. Its native-status
    function returns it, and `RunOutcome.from_status` makes the run's outcome, as for the other three strategies.
  - A provider failure is stored as a run with `execution_status` `provider_error`, whose outcome is `failed`
    ([A.8](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a8-momentum-provider-failure-and-result-status-question-from-ph2-2026-10-07)
    decided). The run keeps its resolution trace and a typed `provider_failure` record. `ExecutionCapture` receives
    the failure, so the automatic provider check still fires, for the direct command and for refresh.
  - `metrics` becomes absent exactly when no calculation ran. The result schema version and the evidence codec
    version are bumped. The Momentum document version is bumped, `momentum.schema.json` is regenerated, and the
    presenter, the JSON document and replay change with it.
  - The mapping of every exception on Momentum's path is in the [table below](#the-exceptions-on-momentums-path-d3).
  - **Short history (D4):** the status is `input_unavailable` whenever the trend is `UNKNOWN`. RSI, when computed,
    is still stored and shown.
  - **User-visible cost:** `ian momentum` exits 1 for a ticker with too little history (`exit_code_of` returns 1 for
    `unavailable` and `failed`), where it exited 0 before. A refresh containing such a ticker exits 1
    (`_refresh_has_failure`), as it already does for an unavailable Graham or FCF-Growth run. A provider failure
    exited 1 before and still does; what changes is that the run is stored and the document is a Momentum document.
  - **`None` is removed from the status type.** After this slice every strategy reports a status, so
    `RunOutcome.from_status`, `ExecutionCapture.native_status`, `StrategyBehavior.native_status`,
    `BehaviorView.native_status_of` and the evaluation runner's status accessor take and return a
    `CalculationStatus` with no `None`. A `None` that nothing returns is a branch that cannot be told from a
    forgotten status ([SWC design §3.3](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#33-behavior-members-and-the-two-tiers)
    gave that reason for making the member required).
- **Scope:** the Momentum package (analyzer, execution, codec, presenter, envelope, replay, CLI), the shared status
  type, the descriptor's versions, the stored outputs and schema, the Momentum golden case that expects the short
  history, and the documents in [B.3](#b3-documentation). The code docstrings that say Momentum reports no status
  are rewritten here: `RunOutcome.from_status`, `ExecutionCapture`, `from_momentum_capture` and
  `momentum_native_status`. The file list is in [B.1](#b1-350a-files).
- **Branch:** `feat/step-3-5-0a-momentum-status` (this branch; plan and implementation are one pull request).
- **Detail:** [A.8 decision](#a1-decisions-d1-to-d11-2026-10-25), [result shape](#b4-momentum-result-shape),
  [files](#b1-350a-files), [tests](#b5-350a-tests).

#### The exceptions on Momentum's path (D3)

Every exception that `MomentumInputResolver.resolve`, `MomentumAnalyzer.run_analysis` and
`compute_momentum_metrics` can raise, read from the code on `main`:

| # | Raised by | Exception | Mapping | `execution_status` | Reason code |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `fetch_historical_data` (the yfinance client, `data/yfinance/client.py`) | `DataFetchError`, classified (`kind` and `provider_id` set) or not | Stored with a `provider_failure` record (none when unclassified) | `provider_error` | `ReasonCode.PROVIDER_ERROR` |
| 2 | the cached client (`data/cached_client.py`), inside the same call | `HistoricalDataQualityError` | As row 5 | `input_unavailable` | none (text reason) |
| 3 | resolver: the day after `as_of` is not after `start_date`; and the frame is empty after the boundary truncation | `NoEligibleObservationsError` | Stored | `input_unavailable` | `ReasonCode.NOT_AVAILABLE_AS_OF` |
| 4 | resolver: provider data, or its live future-observation check (when `as_of` is not given) | `HistoricalDataQualityError` | As row 5 | `input_unavailable` | none (text reason) |
| 5 | analyzer: the second quality check on the frame handed to calculation | `HistoricalDataQualityError` | One mapping for a failed quality check, whatever rule failed; the rules are not mapped one by one | `input_unavailable` | none (text reason) |
| 6 | calculation: trend `UNKNOWN` (the long average needs more observations than the series holds) | not an exception: `TrendStatus.UNKNOWN` | Stored with metrics | `input_unavailable` | `ReasonCode.INSUFFICIENT_HISTORY` |
| 7 | resolver | `ValueError("Momentum as_of must be timezone-aware.")` | Keeps raising: a caller defect, checked earlier by `_parse_as_of` | none (raises) | none |
| 8 | resolver | `ValueError("Momentum market-data provider identity is required.")` | Keeps raising: wiring, not the inputs | none (raises) | none |
| 9 | analyzer | `require_ticker` `ValueError`, `MomentumConfig` validation errors | Keep raising: the request, not the inputs | none (raises) | none |
| 10 | `compute_momentum_metrics` | `ValueError` from an empty frame, `ValueError` for a non-finite latest close | Keep raising: guards of a pure function. Neither is reachable through the analyzer, because `historical.numeric` fails first on an empty frame, a missing `Close` column or a non-finite value (`data/quality.py`, `_numeric_error`), and that is row 4 or 5 | none (raises) | none |
| 11 | any layer | any other exception, including `ResolvedInput` and `MarketDataContext` invariant errors | Keep raising: a defect, per [Shared definitions §2](STEP_3_5_SHARED_DEFINITIONS.md#result-level-status) | none (raises) | none |

- **Precedent for row 5:** the shared financial resolver turns a failed quality check into `input_unavailable` with a
  text reason and no `ReasonCode` (`data/financial/resolver.py`, where `financial_quality_error`'s message becomes
  `(CalculationStatus.INPUT_UNAVAILABLE, error)`). FCF-Growth's `_fact_rejection` returns the same status. The failure
  envelope agrees: `HISTORICAL_QUALITY` and `NO_ELIGIBLE_OBSERVATIONS` are in `INPUT_UNAVAILABLE_CODES`.
- **Why no code for a quality failure:** no member of `ReasonCode` fits, and the project owner decided on 2026-10-25
  to add none. The reason is text only, the message `HistoricalDataQualityError` already builds (field and date
  evidence, no raw observations). The `FailureReasonCode` `historical_quality` still names the same failure when it
  is raised elsewhere.
- **Provider text:** the stored reason for row 1 is a fixed message. The provider's exception text is not stored,
  because it may carry provider data; the `provider_failure` record holds the kind and the provider.
- **Where it is decided:** the resolver catches rows 1 to 4 and returns a failed resolution; the analyzer applies row
  5 and row 6. The calculator is unchanged and still pure.

### 3.5.0b — Side-by-side refresh table

- **Problem:** a refresh runs several strategies over a watchlist and records one `refresh_id`, but its results
  can only be inspected run by run. Every new strategy would otherwise have to bring a headline of its own later,
  as a retrofit of eleven.
- **Decision (D1, D5 to D11):**
  - One command, `ian runs compare <refresh-id>`, in the `runs` group of `cli_workspace.py`. It takes the full UUID
    that `refresh` prints and has `--json`, with a typed model (`RunsCompareDocument`, `schema_version` 1, in
    `workspace_documents/runs_compare.py`) and a checked-in schema (`schemas/runs-compare.schema.json`).
  - The table is rebuilt from storage only: no provider, cache, clock or recalculation. It adds no persistence, batch
    ID or run type.
  - The `headline` member is added to the behavior bundle with the types of the SWC design; the types live in a new
    `reporting/headline.py`, the builder and its document in `workspace_documents/`, with the headline functions
    injected. Both placements fit the package table in [ARCHITECTURE §13](../../../ARCHITECTURE.md#13-module-boundaries)
    and add no import between units.
  - `AGENTS.md` §0 is removed in the first commit of this sub-slice ([A.1](#a1-decisions-d1-to-d11-2026-10-25), D5).
    Its stored-data rule is replaced by a permanent rule in §4 (E1), which also decides how the table treats a run
    stored under an older version (see the [table rules](#table-rules-d7)).
  - Rows, columns, empty cases and the failure cases are in the [table rules](#table-rules-d7).
  - The text layout is in the [rendered example](#rendered-text-example-d9); the cells are in the
    [headline cells](#headline-cells-of-the-four-existing-strategies-d8-d9).
- **Scope:** `AGENTS.md` §0 removal and the two permanent §4 rules; `reporting/headline.py`; the `headline` member
  of `StrategyBehavior` and `BehaviorView` with `headline_for`; `headline_<strategy>` in each existing strategy's
  `replay.py`; one new repository read; the builder, the document, the renderer and the command, in
  `workspace_documents/runs_compare.py` and `cli_workspace.py`; the generator template, the site data file, the
  specimen strategy and the member set T15 checks, updated once for the new member; the contributor guide,
  regenerated; tests; `WORKSPACE.md`, `USAGE.md` and `GLOSSARY.md`. The file list is in [B.2](#b2-350b-files).
- **Branch:** `feat/step-3-5-0b-side-by-side-table`, off `main` after the 3.5.0a pull request merges.
- **Detail:** [files](#b2-350b-files), [tests](#b6-350b-tests),
  [Shared definitions §10](STEP_3_5_SHARED_DEFINITIONS.md#10-side-by-side-refresh-table),
  [Slice inputs §2](STEP_3_5_SLICE_INPUTS.md#2-350--side-by-side-refresh-table).

#### Table rules (D7)

- **Rows:** the tickers, in watchlist order: each ticker's lowest `batch_position` among its runs. The current
  watchlist is never consulted, so a watchlist edited after the refresh changes nothing.
- **Columns:** the strategies present in that refresh's runs, in `STRATEGIES` order.
- **A missing pair** (a ticker with no run for a strategy that other tickers have) shows "no stored run".
- **Exit code:** 0 whenever the table renders, whatever the outcomes of the runs in it. A `failed` run is a row
  of the table, not a failure of the command.
- **Unknown ID or a `--no-save` refresh:** storage cannot tell them apart, so one message covers both, without
  guessing which: "No runs are stored for refresh `<id>`. The ID is unknown, or the refresh was run with
  `--no-save`." It is reported through the failure envelope with `FailureReasonCode.ANALYSIS_RUN_NOT_FOUND`
  (`analysis_run_not_found`, status `error`), exit 1.
- **Two runs for one ticker and strategy** (a watchlist can hold two Momentum selections for one ticker) refuse the
  table through the failure envelope with `FailureReasonCode.INVALID_INPUT` (`invalid_input`), exit 1, and the
  message names every duplicated ticker and strategy. `invalid_stored_run` is not used, because the stored runs
  are valid; the refresh simply holds more than the table can show.
- **Malformed argument:** the existing run-ID parser, `InvalidParameterError` (`invalid_parameter`).
- **A run the table cannot read (E3).** `decode_evidence` raises `UnsupportedRunVersionError` for a run stored under
  an older version and for a run of a strategy no longer declared, and `InvalidStoredRunError` for evidence that is
  invalid. The two are different exception types, so the table tells them apart:
  - **Older version, or strategy no longer declared:** the table still renders and the exit code stays 0. The run's
    outcome is read from the stored envelope's `status`, which needs no decoding, and its cells show "—". A line
    below the table names the IDs of the runs that could not be read for these reasons. In `--json` the run's
    `headline` is null and `headline_unavailable` says why (`unsupported_version` or `strategy_not_declared`). A run
    of a strategy no longer declared follows the declared columns, in a column named by its stored method identifier.
    The version rule is applied to the indexed columns first, so a run of an older version is recognized without
    decoding an envelope whose other fields may no longer parse. The realistic case is a Momentum run stored before
    3.5.0a (result schema 4, evidence codec 3).
  - **Invalid evidence, or an envelope that is malformed:** the whole table is refused through the failure envelope
    with `invalid_stored_run`, naming the run ID, as `runs show` does.
  - A run that stored no result evidence at all has no headline (`headline_unavailable` `no_result_stored`) and is
    not named in the note, because its outcome already says why.
- **Reading:** a refresh can hold more than the 100-row limit of `RunQuery`, so 3.5.0b adds a read of the full runs
  of one refresh to `SQLiteAnalysisRunRepository` (SQL stays in the repository, per
  [ARCHITECTURE §14](../../../ARCHITECTURE.md#14-contributor-guardrails)).
- **Correction to D6's wording:** the command is a subcommand of the `runs` group. `NON_STRATEGY_COMMANDS`
  (`scripts/strategy_conformance.py`) lists top-level commands only, and T7 does not look inside a group, so an
  entry there would name a command that does not exist at the top level. The entry the command needs is its row in
  `JSON_DOCUMENTS` (`workspace_documents/json_documents.py`), which T21 requires for every `--json` command. The
  contract's 3.5.0 and 3.5.6 sections say so.

#### Headline cells of the four existing strategies (D8, D9)

A cell has a key, a label, a kind, a unit, a value, a status and a reason code. **The label is the text table's
column header, verbatim (E4); there is no separate abbreviation.** **The reason code is set when the
result carries a `ReasonCode` for that cell, and is `None` otherwise** (amended 2026-10-25, [A.1](#a1-decisions-d1-to-d11-2026-10-25)).
The Graham results carry text reasons only, so their cells never have one. **A text cell carries no status and no reason
code** ([SWC design §3.3](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#33-behavior-members-and-the-two-tiers); the
run's status is already shown in the outcome column). A number cell with no value (the run did not calculate) takes
the run's `execution_status` and the run's reason code, if it carries one.
`GN` is `GrahamNumberAnalysis`, `GG` is `GrahamGrowthAnalysis`, `FCF` is `FCFEarningsGrowthResult` and `MOM` is
`MomentumRun`.

| Strategy | Key | Label | Kind | Unit | Value from | Status from | Reason code from |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Momentum | `trend` | Trend | text | none | the word of `TrendStatus.display_name` ("Bullish Trend") without "Trend", the `Status:` line of the concise output (`trend_word` in `presenter.py`); none for `UNKNOWN` and when `metrics` is absent | none (text cell) | none (text cell) |
| Momentum | `rsi` | RSI | number | points | `MOM.metrics.rsi_14.value` | `MOM.metrics.rsi_14.status`; `MOM.execution_status` when `metrics` is absent | `MOM.metrics.rsi_14.reason_code`; `MOM.reason_code` when `metrics` is absent |
| Graham Number | `maximum_indicated_price` | Max price | number | `<currency> per share` | `GN.result.maximum_indicated_price` | `GN.native_status` | none (text reason) |
| Graham Number | `margin_of_safety` | Margin | number | percent | `GN.margin_of_safety_percent` | `GN.price_comparison.status` mapped: `available` is `ok`, `unavailable` is `unavailable`; `GN.native_status` when no comparison exists (`unavailable` if that is `ok`) | none (token reason) |
| Graham Growth | `intrinsic_value` | Value | number | `<currency> per share` | `GG.result.growth_value` | `GG.native_status` | none (text reason) |
| Graham Growth | `margin_of_safety` | Margin | number | percent | `GG.margin_of_safety_percent` | as Graham Number, from `GG.price_comparison` | none (token reason) |
| FCF-Growth | `fcf_cagr` | FCF CAGR (total basis) or FCF/share CAGR (per-share basis) | number | percent | `FCF.fcf_cagr` when the policy's classification basis is total FCF, else `FCF.fcf_per_share_cagr` | that metric's `status` | that metric's `reason_code` |
| FCF-Growth | `eps_cagr` | EPS CAGR | number | percent | `FCF.eps_cagr.value` | `FCF.eps_cagr.status` | `FCF.eps_cagr.reason_code` |
| FCF-Growth | `classification` | Class | text | none | the word of the concise output's `Screen:` line, `PASS`, `FAIL` or `INDETERMINATE` (`screen_word` in `presenter.py`) | none (text cell) | none (text cell) |

- **Text values come from the strategy's own concise output (E4).** Momentum's trend is "Bullish" or "Bearish", the
  word of the `Status:` line ("Bullish Trend") without the word the column header already says; `UNKNOWN` is no value
  and shows "—". FCF-Growth's class is the word of the `Screen:` line. Neither is a second spelling of an enum value.
- **The FCF CAGR cell names its basis.** The classification basis is a per-run option (`--classification-basis`).
  The cell keeps the stable key `fcf_cagr`, and its label names the run's basis: "FCF CAGR" for total FCF, "FCF/share
  CAGR" for per share. The text table uses the label as the column header, so a column that holds both bases reads
  "FCF CAGR / FCF/share CAGR". This replaces the per-value marker and legend line of amendment A2 (E4).
- **Currency (owner decision, 2026-10-25).** An `ok` Graham value does not always have a currency: an override
  (`--eps`, `--bvps`) carries none, and a Graham Number with both overridden, or a Graham Growth with `--eps`, has no
  currency. A per-share cell is therefore written by `format_money` of `reporting/presentation.py`, in every case, so
  the currency follows the number: "142.10 USD", or "142.10 (currency unspecified)" when none was recorded. In
  `--json` the unit keeps the form "<currency> per share" and is "currency unspecified per share" when none was
  recorded. The table never shows a bare per-share number, and no currency is taken from another input.
- **Reason text is not a cell field.** A Graham cell with a non-`ok` status shows "—" in the text table and its
  status in `--json`; the reason is read with `ian runs show <run-id>`, which the run ID below the table points to.

| Strategy | Period end | Taxonomy |
| :--- | :--- | :--- |
| Momentum | not recorded (it has no fiscal period) | not recorded |
| Graham Number | the observation period end of the earnings (EPS) input: the newest of the three annual periods it averages; not recorded when EPS was an override (`--eps`), which carries no period. Label: "earnings input period end" | not recorded |
| Graham Growth | the observation period end of the EPS input; not recorded when it was an override. Label: "earnings input period end" | not recorded |
| FCF-Growth | the recorded `period_end` of the selected span. Label: "selected span end" | not recorded |

- **A period end carries its label.** `Headline` has a `period_end_label`, set by each strategy that has a period end,
  so that the table never shows a period end under a plainer name than the strategy gives it. A period end without a
  label is refused by the type. This field is an addition to the type in the SWC design (§3.3), made here (decision
  in [A.1](#a1-decisions-d1-to-d11-2026-10-25)).

- **Taxonomy is "not recorded" for all four.** It is never derived from the prefix of a `provider_field`.
- **BVPS and EPS can differ in period.** No code compares them. Graham Number's EPS is the three newest eligible
  annual EPS periods (`resolve_three_year_average_eps`), while its BVPS is derived from the fiscal-year-end equity
  and share components of the latest eligible balance sheet (`resolve_bvps`), which are checked only against each
  other. If the newest filing lacks a diluted EPS fact, EPS comes from an earlier year than BVPS. D8's rule stays,
  and the table says what it shows: the period line for Graham Number and Graham Growth is labelled "earnings
  input period end", never plain "period end". The rule is therefore true and not misleading, and the case is rare.

#### Rendered text example (D9)

The text is the command's own output over a stored test refresh, with the run IDs shortened and the tickers renamed.
It is the layout the owner approved ([A.1](#a1-decisions-d1-to-d11-2026-10-25)), amended by E4 and the currency
decision. Three tickers, one refresh over all four strategies. ACME completes everywhere. BOLT has too little history
for Momentum's long average (the trend is "—", the RSI is still shown), missing inputs for Graham Number, no stored
Graham Growth run, and an FCF-Growth run with no annual facts. CRUX's Momentum price provider failed, and that run was
stored under an older version, so its cells read "—" and a line below the table names it; its Graham Number and Graham
Growth runs failed, and its FCF-Growth run is on the per-share basis, so the FCF column's header names both bases.

```text
Refresh 3f1c0b52-6f6e-4c52-9a52-0d3e8f4a1b77 · watchlist "Core" · 3 tickers · 4 strategies

         Momentum                      Graham Number                       Graham Growth                     FCF Growth
Ticker   Trend     RSI    Outcome      Max price      Margin  Outcome      Value          Margin  Outcome    FCF CAGR / FCF/share CAGR  EPS CAGR  Class          Outcome
ACME     Bullish   100.0  completed    36.69 USD      —       completed    66.28 USD      —       completed  10.2%                      17.6%     PASS           completed
BOLT     —         100.0  unavailable  —              —       unavailable  no stored run  —       —          —                          —         INDETERMINATE  unavailable
CRUX     —         —      failed       —              —       failed       —              —       failed     10.2%                      17.6%     PASS           completed

Period ends
  ACME     Graham Number: earnings input period end 2024-06-30 · Graham Growth: earnings input period end 2024-06-30 · FCF Growth: selected span end 2025-01-01
  BOLT     Graham Number: earnings input period end — · FCF Growth: selected span end —
  CRUX     Graham Number: earnings input period end — · Graham Growth: earnings input period end — · FCF Growth: selected span end 2025-01-01

Could not be read (stored under an older version, or for a strategy no longer declared): d32e...

Runs (open one with: ian runs show <run-id>)
  ACME     momentum       aea5...
  ACME     graham-number  0b45...
  ACME     graham-growth  4922...
  ACME     fcf-growth     600f...
  BOLT     momentum       b509...
  BOLT     graham-number  d9fa...
  BOLT     fcf-growth     5575...
  CRUX     momentum       d32e...
  CRUX     graham-number  78c7...
  CRUX     graham-growth  3ebb...
  CRUX     fcf-growth     9f06...
```

- **The table holds the headline cells and the outcome of each strategy.** Period ends and run IDs are listed
  below it, one run per line with the full ID, because `runs show` takes the full UUID.
- **The header of a column is its cell's label (E4).** A column that holds runs of both FCF bases is headed by both
  labels. A strategy none of whose runs could be read has an `Outcome` column only.
- **A missing pair** shows "no stored run" in the strategy's first cell column and "—" in the rest of its columns.
- **Period ends** are listed per ticker in the strategy's own words ("earnings input period end", "selected span
  end"); Momentum has none and is not listed.
- **The taxonomy line is left out of the text** while no run records one. `--json` carries the field.
- **Requested `as_of` dates are shown only when the refresh holds more than one:** a line "Requested as-of:" naming
  each. Here every run has none, so the line is absent. `--json` always carries `requested_as_of` per run.
- **`--json` carries every field:** per run, the run ID, outcome, requested `as_of`, each cell with key, label, kind,
  value, unit, status and reason code, the period end and the taxonomy; per refresh, the watchlist and the
  strategies in column order.
- **Missing values** are "—". **Units:** percent as `18.4%`, points bare (`61.2`), multiples as `12.3x`, a per-share
  amount by `format_money` (the number, then the currency, as "142.10 USD"). A negative number uses a true minus sign.

## 4. Scope limits

- No formula, threshold or classification changes. Momentum's SMA, crossover and RSI values are identical to the
  stored outputs of today for every input that ran before.
- No new data, provider capability or fiscal-period source; no taxonomy recording for the four existing strategies.
- No ranking, sorting, composite column or cross-strategy weighting; the sort option is 3.5.6.
- No new persistence, batch ID, run type or schema field for the table.
- No change to the failure handling of the instrument-profile composition that runs before Momentum's analyzer.
- No change to `AnalysisRun.native_status` and `native_reason` (the envelope fields `execute` never sets).
- No reason text field on a headline cell; no per-cell drill-down other than the run ID.
- No new `CalculationStatus`, `ReasonCode` or `FailureReasonCode` member.
- The one-line-per-ticker text layout is about 170 characters wide over four strategies (the example above is 174 to
  186) and would be about 460 over eleven. The slice that adds the fifth strategy, 3.5.3, decides the text layout for more strategies. `--json` is
  unaffected.
- No work on the new strategies. The record of where `docs/TOOL_DEVELOPMENT.md` fell short stays with 3.5.3; 3.5.0b
  records in its own implementation record every shortfall it meets, for the 3.5.3 plan to link (D11).

## 5. Acceptance criteria

**3.5.0a**

- A provider failure, a failed quality check and an empty history each store a run, and a short history stores a
  run with the trend `UNKNOWN`, RSI where it was computed, and `input_unavailable`. Outcomes: `failed`, `unavailable`,
  `unavailable`, `unavailable`.
- The automatic provider check fires for a Momentum provider failure from the direct command and from refresh, and
  `--no-provider-check` suppresses it.
- Every row of the [exception table](#the-exceptions-on-momentums-path-d3) is exercised by a test; the rows that keep
  raising are asserted to raise.
- A previously successful Momentum output differs from today's in the document version, the new non-null fields
  `execution_status` (`ok`), `ticker` and `effective_as_of`, and the new null fields `reason`, `reason_code` and
  `provider_failure`. Momentum's numbers are identical.
- No strategy returns `None` from its native-status function, and no signature in the code accepts it.
- The complete managed gate passes, with at least 85% coverage and every new branch exercised.

**3.5.0b**

- The table for a stored refresh over the four strategies equals the reviewed cells, with provider, cache, clock and
  calculator disabled.
- The empty, duplicate, missing-pair and mixed-outcome cases behave as the [table rules](#table-rules-d7) state.
- The rendered text matches the approved layout; `--json` validates against the checked-in schema.
- T7, T8, T15, T16, T20, T21 and the site checks pass with the new member, and the specimen strategy carries it.
- `AGENTS.md` §0 is gone, and no document still says it is in force.
- The complete managed gate passes.

## 6. Background

Step 3.5 adds seven screening strategies, and the side-by-side table was moved to the front of the step so that the
`headline` member exists before any new strategy is written
([A.7](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a7-build-order-and-result-status-2026-10-03)). PH.2 found that Momentum
raises a provider failure where the other three store it, and left the question to the result-level status
decision ([A.8](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a8-momentum-provider-failure-and-result-status-question-from-ph2-2026-10-07)).
Writing this plan against the code showed that the table cannot be built honestly first: its cells need a status and
a reason on every run, and a Momentum refresh job that raises has no run to show. The slice was therefore split.

---

## Appendix A: Decision records

### A.1 Decisions D1 to D11 (2026-10-25)

Approved by the project owner. Each is stated in the sections above; this table records them.

| # | Topic | Decision |
| :--- | :--- | :--- |
| D1 | Structure | One plan, written on the 3.5.0a branch. 3.5.0a is implemented there, as one pull request. 3.5.0b has its own branch off `main` after that merges. The contract's sequence table has rows 3.5.0a (In progress) and 3.5.0b (Planned) in place of 3.5.0; the milestone plan's Step 3.5 row is In progress. |
| D2 | A.8 | A provider failure is a stored run with `execution_status` `provider_error`; outcome `failed`; resolution trace kept; the failure passed to `ExecutionCapture`; versions bumped; no compatibility code. |
| D3 | Other exceptions | Mapped in the [exception table](#the-exceptions-on-momentums-path-d3). |
| D4 | Short history | `input_unavailable` whenever the trend is `UNKNOWN`; RSI stored and shown; the exit-code cost is stated. |
| D5 | `AGENTS.md` §0 | Removed in the first commit of 3.5.0b, not 3.5.0a: Momentum's stored shape changes in 3.5.0a without compatibility code, which §0 permits and nothing after §0 would. The contract's entry condition is amended to match. |
| D6 | Command | `ian runs compare <refresh-id>`; typed `--json` model; checked-in schema; the `JSON_DOCUMENTS` entry (see the correction above). |
| D7 | Rows, columns, empty cases | The [table rules](#table-rules-d7). |
| D8 | Period end and taxonomy | As in the cell tables; taxonomy "not recorded" for all four. |
| D9 | Text layout | The rendered example, for approval; the cell tables. |
| D10 | Placement | `reporting/headline.py` for the types; builder and document in `workspace_documents/`; `headline` and `headline_for` on `BehaviorView` and `StrategyBehavior`; the generator template, the site data file's replay row, the specimen and T15's member set updated in 3.5.0b. |
| D11 | Guide shortfalls | The record stays with 3.5.3. 3.5.0b regenerates the guide and records its own shortfalls for 3.5.3's plan to link. |

Decided during planning, also 2026-10-25:

| Topic | Decision |
| :--- | :--- |
| Reason code of a quality failure | No new code. The shared financial resolver is the precedent: a failed quality check is `input_unavailable` with a text reason and no `ReasonCode`. Momentum's failed quality check is one mapping, not one per rule. |
| `HeadlineCell.reason_code` | Set when the result carries a `ReasonCode` for that cell, `None` otherwise. The rule is amended in [Slice inputs §2](STEP_3_5_SLICE_INPUTS.md#2-350--side-by-side-refresh-table) and the [SWC design §3.3](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#33-behavior-members-and-the-two-tiers). |
| Failure codes of the command | `analysis_run_not_found` for an unknown or unsaved refresh; `invalid_input` for two runs of one ticker and strategy. Both exist. |
| `None` status | Removed from the status types in 3.5.0a. |

Approved by the project owner on review of the plan (2026-10-25):

| Topic | Decision |
| :--- | :--- |
| D6's wording | The command's entry is its row in `JSON_DOCUMENTS` (`workspace_documents/json_documents.py`), which T21 requires. The contract's 3.5.0 and 3.5.6 sections are corrected to say so, in place of "an entry for the command in the SWC command test's non-strategy list". |
| Rendered text layout (D9) | Approved, with the FCF CAGR basis marker and its legend line, and the layout-width limit decided by 3.5.3. |
| Amendments A1 to A6 | Text cells carry no status; the FCF CAGR cell names its basis; the stale `None` text of the SWC design joins 3.5.0a's documentation scope; the unchanged-output criterion is corrected; the text layout limit is recorded; "fixed sentence" becomes "fixed message". |

Approved by the project owner for 3.5.0b (2026-10-25):

| # | Topic | Decision |
| :--- | :--- | :--- |
| E1 | Replacement for §0's stored-data rule | §0 is removed entirely. `AGENTS.md` §4, under "Implementation preservation", states a permanent rule: a change to a persisted selection, evidence or result shape bumps its version field; runs stored under an older version stay in the database and are refused by version when read (`UnsupportedRunVersionError`), never misread; no migration or compatibility decoder is written unless the active plan requires one; the pull request lists such a change among its user-visible changes. |
| E2 | "Open items" | §4 states: "Open items" are not an acceptable outcome of a design decision; decide, or escalate to the project owner. §0's other rules are already stated in §3 and §4. |
| E3 | A refresh holding runs the table cannot read | As in the [table rules](#table-rules-d7): an older version or an undeclared strategy renders with the outcome from the stored envelope, "—" cells, a note line and a null `--json` headline, exit 0; invalid evidence refuses the table with `invalid_stored_run`. Both cases are tested; a Momentum run stored before 3.5.0a is the older-version test. |
| E4 | Headers and text values | The text table's column header is the cell's label, verbatim; labels are Trend, RSI, Max price, Margin, Value, Margin, FCF CAGR (or FCF/share CAGR), EPS CAGR, Class. Text values are the words of the strategy's own concise output; Momentum's `UNKNOWN` is no value. This replaces A2's per-value marker and legend line. |
| E5 | The new document | `workspace_documents/runs_compare.py`, `schemas/runs-compare.schema.json`, `RunsCompareDocument`, `schema_version` 1 first among its keys. |
| E6 | Record of guide shortfalls | In the [implementation record](#a3-350b-implementation-record-2026-10-25) below, linked from the 3.5.3 section of the contract. |
| E7 | Commits | Five commits in the order the owner gave. |
| E8 | Sequence tables | 3.5.0b is Complete here and in the contract's §2, and 3.5.1 is Next; the milestone's Step 3.5 row stays In progress. |
| Currency | A per-share cell with no recorded currency | The 3.5.0b check found that an override carries no currency, so an `ok` Graham value can have none. Every per-share cell in the text table is written by `format_money` ("142.10 USD", or "142.10 (currency unspecified)"); the `--json` unit is "<currency> per share" or "currency unspecified per share". |
| Period-end label | Naming the period end | `Headline` gains `period_end_label`, because a period end shown under a plainer name than its strategy gives it would mislead (the Graham strategies' EPS period). Decided by the implementer within the plan's goals; reported to the owner. |

### A.2 Premises checked against the code (2026-10-25)

| Premise | Finding |
| :--- | :--- |
| Another strategy's provider failure ends as a stored `failed` run | Holds. Graham Number and Graham Growth record `assembly.provider_failure`; FCF-Growth records `provider_failure` on its result; each status maps to `failed` by `RunOutcome.from_status`. |
| A refresh job that raises stores no run | Holds. `_failed` records an `error` result with no run. |
| Momentum raises only what D3 maps | Holds; every raise is a row of the exception table. |
| A precedent for a failed quality check exists | Holds: `data/financial/resolver.py` and `fcf_growth/input_resolver.py`; both give `input_unavailable`. |
| D10's placement keeps the package table | Holds: `reporting` and `workspace_documents` already import what the new modules need. |
| An entry in the SWC command test's non-strategy list | Does not apply to a subcommand; corrected above and in the contract. |
| Each cell carries a `ReasonCode` when not `ok` | Does not hold for the Graham cells, whose results carry text reasons; the rule is amended. |
| An `ok` Graham value always has a currency | Does not hold: an override carries none (`--eps` and `--bvps` for Graham Number, `--eps` for Graham Growth). The unit and the text say so, as the currency decision above states. |
| The EPS input's observation period end can be read from the stored Graham result | Holds: the derived EPS input records `observation_period_end` (the newest of its three periods), and the codec keeps it. |
| `decode_evidence` can tell an older-version run from invalid evidence | Holds: `UnsupportedRunVersionError` and `InvalidStoredRunError` are different types. A run for a strategy no longer declared raises the first. |

### A.3 3.5.0b implementation record (2026-10-25)

**Contributor guide shortfalls (E6).** `docs/TOOL_DEVELOPMENT.md` describes how to add a strategy. Adding a member to
the behavior bundle, which 3.5.0b did, is a change to the contract, and the guide does not cover it. Every point
below was found by a failing test or by reading the code, not from the guide. 3.5.3's plan links this record.

1. **The guide ran ahead of the code.** The `replay` row's title already said "Replay projector and headline
   function", but nothing generated a headline function and the row's `defines` pattern checked `project_.+` only. The
   row now says what the file holds, and checks `headline_.+` too.
2. **A new bundle member touches files the guide never names:** `strategy_wiring.py` (the member, the view's accessor and
   `headlines_by_key`), `scripts/strategy_conformance.py` (the closed member set, the view accessor set and the
   exact-type probes), `scripts/new_strategy.py` (the generated behavior declaration and its import),
   `scripts/strategy_templates/replay.py.tmpl`, `tests/specimen/behavior.py` and `tests/specimen/replay.py` (the
   specimen implements the erased view by hand), and `tests/scripts/generator_fills/replay.py.fill`. A reader finds
   them from the failures of T15, T16 and the generator's end-to-end test, one at a time. 3.5.3 should expect the same
   when it changes the envelope.
3. **A fill repeats the template's signatures.** `tests/scripts/generator_fills/codec.py.fill` held its own copy of
   `native_status`'s return type, so removing `None` from the status types in 3.5.0a was found by the end-to-end test,
   not by the template change. Fills are not generated from the templates.
4. **The pinned table of failure codes.** `tests/_failure_code_table.py` requires every exception class that declares
   a `reason_code` to be pinned. The guide does not mention it for a new command that needs a new failure. 3.5.0b
   avoided the file: the command reports its two failures through the failure envelope without a new class code.
5. **Regenerating a command's stored output.** The guide names the two regeneration commands for the direct commands'
   output and the stored strategy documents, but not `uv run python -m tests._workspace_command_output`, which a new
   workspace command needs, and the scenario's step list in `tests/_workspace_command_output.py` is edited by hand.
6. **The two regeneration entry points ran outside the suite's provider-check switch.** Fixed in 3.5.0a's follow-up; a
   third entry point (`_workspace_command_output`) uses only fixtures that cannot fail on a provider, so it needs no
   switch, but the guide does not say which entry points need one.

**Decisions taken during implementation, for the owner's review.**

- `Headline` gained `period_end_label` (see the A.1 table). The SWC design §3.3, the Shared definitions §10 and the
  Slice inputs §2 describe the type without it; they are not edited here, and the plan above is the authority.
- A per-share cell is formatted by `format_money` in every case, and its `--json` unit says when no currency was
  recorded (owner decision, recorded above).
- A column that mixes FCF bases is headed by both labels, joined with " / ". The alternative, the first run's label,
  would mislabel the others.
- Momentum's text value drops the word "Trend" from the concise output's `Status:` line. The alternatives were the
  full "Bullish Trend", which repeats the column header, and a second spelling of the enum.
- The scenario helper `tests/_workspace_command_output.py` and the stored `runs-compare*.txt` files were added within
  B.2's stored-outputs row. No existing stored output changed.
- The text table's width: the example is 174 to 186 characters (the plan said about 150); 3.5.3 decides the layout for
  more strategies, as the scope limit says.

---

## Appendix B: File inventories, tests and documentation

### B.1 3.5.0a files

Paths are under `investment_analysis_engine/` unless they start with `tests/`, `schemas/`, `docs/` or `scripts/`.

| Area | File | Change |
| :--- | :--- | :--- |
| Analyzer | `strategies/momentum/analyzer.py` | `MomentumRun` gains the fields in [B.4](#b4-momentum-result-shape); `MomentumResolution` carries a status; the resolver catches rows 1 to 4; the analyzer applies rows 5 and 6; `compute_momentum_metrics` is unchanged |
| Execution | `strategies/momentum/execution.py` | `from_momentum_capture` passes the status and the provider failure; `capture_momentum` handles absent metrics; module docstring |
| Codec | `strategies/momentum/codec.py` | evidence validation reads `run.ticker`; status invariants; `momentum_native_status` returns the status; `momentum_ticker` |
| Presenter | `strategies/momentum/presenter.py` | `MomentumPresentation` takes the run's status; concise, details, diagnostics and JSON for every status |
| Envelope | `strategies/momentum/envelope.py` | document version 9 to 10; the result part is nullable; `reason` and `reason_code`; header `status` and `provider_failure` filled |
| Replay | `strategies/momentum/replay.py` | passes the status and reason; no metrics |
| CLI | `strategies/momentum/cli.py` | the command renders from the run's status, prints non-`ok` concise and details output to standard error as Graham does, attaches the provider check, exits by `exit_code_of`; `refresh` is unchanged in shape |
| Tool | `strategies/momentum/tool.py` | no code change; the handler now returns the status-bearing run |
| Wiring | `strategy_wiring.py` | Momentum's `result_schema_version` 4 to 5 and `evidence_codec_version` 3 to 4; the `native_status` type |
| Status types | `analysis/run_models.py`, `workspace/capture.py`, `evaluation/runner.py`, `scripts/new_strategy.py`, `scripts/strategy_sites.toml` | `None` removed; docstrings and site text; the generated table in `docs/TOOL_DEVELOPMENT.md` regenerated |
| Golden suite | `evaluation/cases/momentum.py`, `evaluation/catalog.py`, `tests/evaluation/test_catalog.py` | MOM-02 expects `input_unavailable`; suite version bump under the maintenance rules |
| Stored outputs | `tests/expected_output/direct_commands/momentum.*`, `tests/expected_output/strategy_documents/momentum-*`, `schemas/momentum.schema.json` | regenerated by the commands in the contributor guide, then read |
| Docs | see [B.3](#b3-documentation) | |

TOOL_DEVELOPMENT edit-site rows touched (by site id): `analyzer`, `descriptor`, `codec`, `execution`, `cli`,
`presenter`, `envelope`, `replay`, `cases`, `catalog`, `direct-output`, `strategy-documents`, `schema`, `guide`.
Untouched, and checked by the conformance tests: `vocabulary`, `settings`, `tool-name`, `tool`, `unions`,
`selection`, `cli-tier`, `evaluation`, `evaluation-tier`, `help-snapshot`, `watchlist-options`, `strategy-docs`.

### B.2 3.5.0b files

| Area | File | Change |
| :--- | :--- | :--- |
| Policy | `AGENTS.md`, `tests/test_documented_conventions.py` | §0 removed and the two §4 rules added, in the first commit; the test drops its look-up of section 0 and asserts that none exists |
| Types | `reporting/headline.py` (new) | `CellKind`, `HeadlineCell`, `Headline`, the unit constants, with the invariants of the cell tables |
| Bundle | `strategy_wiring.py` | `headline` on `StrategyBehavior`; `headline_for` on `BehaviorView` with the exact-type guard; the four declarations; `headlines_by_key` |
| Strategies | `strategies/{momentum,graham_number,graham_growth,fcf_growth}/replay.py` | `headline_<strategy>` |
| Read | `workspace/repositories/analysis_runs.py` | `list_refresh_runs`: the runs of one refresh in batch order, as `StoredRefreshRun` records whose envelope decodes on demand |
| Table | `workspace_documents/runs_compare.py` (new) | the builder, the typed document, the text renderer |
| Documents | `workspace_documents/json_documents.py`, `schemas/runs-compare.schema.json` | the `JSON_DOCUMENTS` entry and the schema |
| Command | `cli_workspace.py` | `runs compare` |
| Generator | `scripts/strategy_templates/replay.py.tmpl`, `scripts/strategy_sites.toml`, `scripts/strategy_conformance.py` | the `headline_` name pattern in the replay row and its check; T15's member sets |
| Specimen | `tests/specimen/` | a `headline` for the specimen strategy |
| Guide | `docs/TOOL_DEVELOPMENT.md` | regenerated; shortfalls recorded in the implementation record |
| Stored outputs | `tests/_workspace_command_output.py`, `tests/expected_output/workspace_commands/` | the scenario's three `runs compare` steps and their stored output; the help snapshots do not cover the `runs` group, so none changes |
| Docs | see [B.3](#b3-documentation) | |

TOOL_DEVELOPMENT edit-site rows touched: `replay` (the headline function), `descriptor` (the `headline` argument of
each behavior declaration), `schema` (the new document's schema is produced by the same command), and the generated
rows of the guide. The new command is not a strategy: it has no descriptor, no CLI-tier entry and no tool.

### B.3 Documentation

| Document | 3.5.0a | 3.5.0b |
| :--- | :--- | :--- |
| `docs/user/strategies/MOMENTUM.md` | status, exit codes, the stored failure runs, short history | |
| `docs/user/WORKSPACE.md` | refresh shows a stored Momentum failure | the table and `runs compare`, with the text example, the older-version rule and the `--no-save` and duplicate cases |
| `docs/user/USAGE.md`, `docs/user/GLOSSARY.md` | exit code and status wording for Momentum | `runs compare` in the list of `--json` commands; the term "headline" |
| `docs/user/FINANCE_MATH.md` | none: no formula changes | none |
| `docs/TOOL_DEVELOPMENT.md` | the native-status wording, regenerated | regenerated |
| The Step 3.5 shared definitions and SWC design | updated by the planning commit | none |
| `SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md` §3.3 and §7 | the §3.3 member table's `native_status` row: its type `str \| None` becomes `CalculationStatus`; the §7 escape-hatch row "Momentum has no native failure-status classifier" is rewritten. The §6 inventory row and the Appendix line near "Momentum's `None` is unchanged" are historical records and stay as written | none |

### B.4 Momentum result shape

```text
MomentumRun (frozen dataclass; fields added or changed marked +)
  + ticker: str                              normalized; the run no longer depends on metrics for it
  + effective_as_of: datetime                aware; equals metrics.timestamp when metrics exist
  + execution_status: CalculationStatus
  + reason_code: ReasonCode | None
  + reason: str | None
  + provider_failure: ProviderFailureRecord | None
  ~ metrics: MomentumMetrics | None          absent exactly when no calculation ran
    market_data: MarketDataContext           the empty context when no series resolved
    price_inputs: tuple[ResolvedInput, ...]  empty when no series resolved
    resolution_trace: ResolutionTrace        kept in every case, with its error or rejection event
    instrument_profile, data_resolution      unchanged

Invariants
  ok                       metrics present, trend BULLISH or BEARISH, reason and reason_code None
  input_unavailable        reason non-empty; metrics present with trend UNKNOWN (reason_code insufficient_history),
                           or metrics absent (reason_code not_available_as_of, or None for a quality failure)
  provider_error           metrics absent; reason non-empty; reason_code provider_error;
                           provider_failure only for a classified failure
  other statuses           not produced by Momentum; rejected by the invariant
  provider_failure         only with provider_error
```

### B.5 3.5.0a tests

- **Each row of the exception table**, one test per row, including the four provider kinds and the unclassified
  failure (row 1), the cached-client path (row 2), both sites of row 3 and `as_of` before the history start, the live
  future-observation check (row 4), the second check (row 5), and the rows that keep raising (7 to 11).
- **Guards:** a series with a `NaN` latest close and an empty series are quality failures, not raises, which proves
  row 10 is unreachable through the analyzer.
- **Short history:** the series length exactly the long window (`ok`) and one less (`input_unavailable`); RSI present
  with a short long-average history, RSI absent when the series is not longer than the RSI period.
- **Codec:** round trip for every status; strict decode rejects an `ok` run without metrics, an unavailable run
  without a reason, a `provider_failure` without `provider_error`, an unknown status and a payload of the old
  version.
- **Capture and outcome:** `from_momentum_capture` for every status; the stored run's `status`, `failure_reason_code`
  and `native_status` accessor; `None` rejected by the types.
- **Provider check:** fired for the direct command (standard error lines, and `provider_check` in `--json`) and for
  refresh (summary), and suppressed by `--no-provider-check`.
- **Direct command:** exit codes 0, 1 and 1 for completed, unavailable and failed; concise and details output of a
  non-`ok` run on standard error; `--save-run` of a failed run stores it.
- **Refresh:** a job with a provider failure stores a `failed` run with its batch context; the counts; `--no-save`
  gives a `failed` outcome with its code; sequential and concurrent admission.
- **Presentation:** the four modes for each status; replay equals the direct document; the JSON validates against the
  regenerated schema.
- **Evaluation:** `native_status_of` returns the status for every run; MOM-02 expects `input_unavailable`; the
  telemetry `calculation_status` value.
- **Unchanged output:** the stored outputs of the successful cases differ from today's in the document version, the
  new non-null fields `execution_status` (`ok`), `ticker` and `effective_as_of`, and the new null fields `reason`,
  `reason_code` and `provider_failure`; every number is identical.

### B.6 3.5.0b tests

- **Headline functions:** for each of the four strategies, the reviewed cells of a stored run of every outcome the
  strategy can have; the invariants of `HeadlineCell`; a Graham cell with a non-`ok` status has no reason code.
- **Builder, with provider, cache, clock and calculator disabled:** rows in watchlist order by lowest
  `batch_position`; columns in `STRATEGIES` order; a missing pair; a `failed` run does not drop its row; differing
  fiscal year-ends shown, not normalized; a refresh holding one strategy; a watchlist edited after the refresh;
  a refresh larger than the 100-row query limit.
- **Failures:** an unknown ID and a `--no-save` refresh give the same message; two runs for one ticker and strategy
  name the duplicates; both through the failure envelope with the codes above; a malformed ID. The command checks for
  the empty refresh and for the duplicates itself, so that no exception class declares a new failure code.
- **Command:** exit 0 for a table full of `failed` runs; the text equals the reviewed layout, including the
  more-than-one `as_of` line; `--json` validates against the schema and equals the text's content.
- **Wiring:** `headline_for` rejects another strategy's result (T11); T15's member sets; T16 reads `headline_for`;
  T8 replay; T20 and T21 for the schema and the `JSON_DOCUMENTS` entry; the generator's end-to-end test with the new
  template; the site check for the replay row; the specimen strategy's headline.
- **Runs the table cannot read (E3):** a Momentum run stored before 3.5.0a keeps its row, shows its outcome from the
  stored envelope and is named below the table, with a null `--json` headline and exit 0; a run of a strategy no
  longer declared follows the declared columns; a run with invalid evidence and a run with a malformed envelope each
  refuse the table with `invalid_stored_run`, naming the run.
- **The currency decision:** a Graham Number with `--eps` and `--bvps`, and a Graham Growth with `--eps`, give a unit
  of "currency unspecified per share" and the text "(currency unspecified)"; a reported currency follows the number.
- **Formatting:** percent, points, multiples, a per-share amount and the true minus sign, on synthetic cells.
- **Documents:** the link and sequence-table checks over the updated guide and `WORKSPACE.md`.
