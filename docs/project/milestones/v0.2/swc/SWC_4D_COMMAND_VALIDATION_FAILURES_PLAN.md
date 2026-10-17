# SWC.4d — Command Validation Failures: Slice Plan

Plans the slice that moves every validation failure a command raises itself into the failure envelope, so a
caller meets one failure shape. The slice sits in the [SWC sequence](SWC_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status);
its decision record is [B.14](SWC_CONTRACT_AND_SLICE_PLAN.md#b14-swc4d-command-validation-failures-2026-10-11).

## 1. At a glance

- **What this slice does:** every check a command makes in its own code and rejects with `typer.BadParameter` becomes an
  `invalid_parameter` failure: the sentence on standard error with exit 1, or under `--json` the failure envelope on
  standard output with exit 1. That is 41 raise sites in 8 files, which this plan reads as 45 distinct checks (41 that
  exit 2 today and Momentum's 4 that already exit 1). The envelope gains a `parameters` field naming the offending
  options and arguments.
- **What it does not do:** change a formula or a classification; add `--json` to a command; turn a check into a
  parser-declared constraint; intercept an error the parser raises; rename or repurpose a reason code. After this
  slice exit 2 means one thing: the parser rejected the command line and no command code ran
  ([B.12](SWC_CONTRACT_AND_SLICE_PLAN.md#b12-swc4a-parser-rejected-failures-stay-usage-errors-2026-10-06)).
- **Rules it follows:** each existing sentence is kept except where decision 5 requires the option or argument name
  to appear; a sentence reports and does not instruct unless the existing one already does; no check moves relative
  to another check or to a resource it precedes today; no per-strategy entry in generic tooling; a test fails if
  any file under `investment_analysis_engine/` raises `typer.BadParameter`; the complete managed gate ends step 2.
- **Two steps on one branch:** step 1 (this document) writes the plan and stops; step 2 implements it after the
  project owner has read section F.
- **Where detail lives:** the checks are in [section A](#a-the-check-table), the caught-`ValueError` audit in
  [B](#b-the-valueerror-audit), the shared path in [C](#c-the-mechanism), the Graham messages in
  [D](#d-the-pydantic-derived-graham-messages), the step 2 file list in [E](#e-file-scope-tests-and-documents-for-step-2),
  and the open items in [F](#f-findings-that-do-not-fit-the-decisions). The approved decisions are in
  [Appendix A](#appendix-a-decision-record).

## 2. Steps and status

| Step | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 1 | [Write this plan](#step-1--the-slice-plan) | Complete | 2026-10-11 |
| 2 | [Implement the plan](#step-2--implementation) | Complete | 2026-10-11 |

## 3. The steps

### Step 1 — The slice plan

- **Problem:** a check a command raises itself reaches the caller as plain usage text with exit 2, even under
  `--json`, except Momentum's window checks, which are `invalid_parameter` failures with exit 1.
- **Decision:** the plan lists every check, audits every caught `ValueError` that turns into a usage error, defines
  one shared reporting path and one `parameters` field, and reports what does not fit the approved decisions.
- **Scope:** this document, the SWC.4d section and a new appendix entry in `SWC_CONTRACT_AND_SLICE_PLAN.md`. No
  change under `investment_analysis_engine/` or `tests/`.
- **Branch:** `feat/swc-4d-command-validation-failures`, from `main`. No pull request in this step.
- **Detail:** sections [A](#a-the-check-table) to [F](#f-findings-that-do-not-fit-the-decisions) below.

### Step 2 — Implementation

- **Problem:** as above.
- **Decision:** implement section C once, convert the 45 checks of section A, apply the dispositions of section B,
  bump the failure schema version, and update the documents of section E.
- **Scope:** the files, tests and documents of [section E](#e-file-scope-tests-and-documents-for-step-2).
- **Branch:** the same branch; the pull request is opened only on the project owner's approval.
- **Detail:** sections [A](#a-the-check-table) to [E](#e-file-scope-tests-and-documents-for-step-2).

## 4. Scope limits and acceptance criteria

Scope limits:

- No change to a success document, to the text of a successful run, or to any command's `--help` output.
- No new `--json` option. A command without it reports in text.
- No parser-declared constraint (`min=`, `max=`, `click.Choice`, a required option) replaces a check, and no parser
  error is caught or reworded.
- No reason code is added, renamed, repurposed or removed. Every converted check reports `invalid_parameter`, except `DB-3` (F6),
  ([5.3](#53-invalid_parameter-under-the-stability-rule)); an exception raised inside a workspace command that
  declares no code of its own ([section B](#b-the-valueerror-audit)) reports as `execution_error`.
- No formula, classification or provider behavior changes.
- Stored data shapes do not change. The failure envelope's `schema_version` goes 9 to 10; nothing is migrated.

Acceptance criteria for step 2:

- A test fails when any file under `investment_analysis_engine/` raises `typer.BadParameter`, and a negative control proves the test can fail.
- Every row of section A behaves as its columns say (`DB-3` reports `configuration_error`): exit 1, the sentence in the "after" column on standard error, and
  for a command with `--json` the envelope on standard output, `reason_code` `invalid_parameter` and the stated
  `parameters`, with nothing on standard error.
- A parser rejection (unknown option, wrong type, missing required argument or option, value outside a declared
  choice, unknown command) still exits 2 as text for every command family, with and without `--json`.
- Every `invalid_parameter` sentence contains each name in its `parameters`; a test pins that invariant.
- When two checks would reject one command line, the one that fires today still fires first (section C lists the
  order for each command).
- `parameters` is `null` in every envelope whose `reason_code` is not `invalid_parameter`; the model refuses any
  other combination.
- `schemas/failure.schema.json` is regenerated and its drift check passes; the documents of section E say what
  the code does.
- The complete managed gate passes.

## 5. Checks made before writing

### 5.1 Count and location

The code matches the inventory below. `grep` for `BadParameter`, `UsageError` and `Exit(2)` under `investment_analysis_engine/` finds no
other way a command ends with exit 2. Reading the code found three further ways a check reaches the caller as a
usage error without a `raise typer.BadParameter` line of its own, and those are rows of section A: a
`ValueError` caught from the workspace layer, a `ValidationError` caught by `config_usage_errors`, and the
`ValueError` raised by `require_anchored_path`.

| File | `raise typer.BadParameter` sites | Distinct checks (rows of section A) |
| :--- | ---: | ---: |
| `investment_analysis_engine/cli_support.py` | 9 | 9 (`SUP-1` to `SUP-9`) |
| `investment_analysis_engine/cli_workspace.py` | 16 | 17 (`WRK-1` to `WRK-17`) |
| `investment_analysis_engine/cli.py` (`evaluate`) | 4 | 4 (`EVL-1` to `EVL-4`) |
| `investment_analysis_engine/cli_database.py` | 3 | 3 (`DB-1` to `DB-3`); the in-memory site is two rows by origin (F6), and the second `ValueError` handler is unreachable ([B](#b-the-valueerror-audit)) |
| `investment_analysis_engine/cli_health.py` | 1 | 1 (`HLT-1`) |
| `investment_analysis_engine/strategies/fcf_growth/cli.py` | 5 | 4 (`FCF-1` to `FCF-4`); the currency check is raised at two sites |
| `investment_analysis_engine/strategies/graham_growth/cli.py` | 2 | 2 (`GGR-1`, `GGR-2`) |
| `investment_analysis_engine/strategies/momentum/cli.py` | 1 | 1 (`MOM-5`) |
| `investment_analysis_engine/strategies/graham_number/cli.py` | 0 | 0 (uses the shared helpers) |
| **Total** | **41** | **41** |

The 41 checks exit 2 today. Momentum's four window and period checks (`MOM-1` to `MOM-4`) are
`InvalidParameterError` raises at 4 further sites and already exit 1, so section A has 45 rows once `DB-3` (F6) is counted. `WRK-4`, `WRK-8`, `WRK-10`,
`WRK-14`, `WRK-15` and `WRK-17` are checks that no line of the CLI file raises: a `ValueError` or `ValidationError` from
the workspace layer is caught and re-raised as a usage error ([section B](#b-the-valueerror-audit)).

Two further command-side rejections already reach the envelope and do not change: `AnalysisConfigurationError` for an
unsupported `--data-provider` on the Graham commands (`configuration_error`, exit 1, see F7) and for a missing SEC
identity (a setting, not a parameter).

### 5.2 What `health --json` and `db` write today

| Command | Failure today | Form |
| :--- | :--- | :--- |
| `health --json` | A provider check that does not pass | The `ProviderHealthDocument` (`providers[].verdict`), exit 1. Never a `FailureEnvelope`. |
| `health --json` | Unknown `--provider` | Usage text on standard error, exit 2, no document. |
| `db status --json`, `db upgrade --json` | Readiness failure (`DatabaseReadinessError`) | `DatabaseMaintenanceReport` with `status` `error` and a `reason_code`, exit 1. A sibling shape, not a `FailureEnvelope` ([design §13.1](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#131-decision)). |
| `db status`, `db upgrade` | Invalid `--database-url`, in-memory target | Usage text on standard error, exit 2, with or without `--json`. |

After step 2 a rejected `--provider` or `--database-url` under `--json` writes a `FailureEnvelope`, which is a third
document shape for those commands (F5).

### 5.3 `invalid_parameter` under the stability rule

[Design §13.3](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#133-reason-codes-and-stability) forbids renaming, repurposing or
removing a reason code and changing what it means without a `schema_version` bump and the project owner's approval. The
code can keep its meaning when more checks use it:

- The contract defines the code by what its caller learns: the command's own code rejected the request as given, before any
  work began, the sentence is authored by the command and names the offending parameter, and the caller corrects it and
  retries. Every row of section A satisfies that.
- "Exactly three" in the section "Which option values are invalid parameter today" describes the set at that date. The
  section says the code is `invalid_parameter` "because the command's own code raised `InvalidParameterError`, not
  because the cause is an option value". A consumer written for Momentum's three options, who treats the code as "my
  request is at fault", is right for every new row.
- Three words of the definition are narrower than the new set and are corrected in step 2 (section E): "option" becomes
  "option or argument" (the ticker, a watchlist name, a run ID); "will always fail" becomes "fails as given" (`EVL-4`
  depends on a file existing and `WRK-7` on the terminal); and the "exactly three" paragraph is replaced by a pointer to
  section A.
- The `schema_version` bump (9 to 10) is required by the new `parameters` field, not by this widening.

I found no reason to stop.

## 6. Detail

### A. The check table

Reading the table:

- Each parser-rejected form (a Typer "Usage:" box with `Error  No such option`, `Missing argument` and the like)
  is out of scope and exits 2 before and after.
- "Sentence today" is the text after Typer's `Error  Invalid value:` (or `Invalid value for <hint>:` where the code gave a
  `param_hint`, shown as "hint"). The usage box that surrounds it is not part of the sentence and disappears.
- "Unchanged" means the sentence is kept exactly. Rule R: every sentence in the "after" column contains each name in its
  `parameters`. An option is written with its declared primary long spelling (`--expected-growth`), an argument with the upper-case
  name the existing sentences use (`TICKER`, `NAME`, `NEW_NAME`, `INDEX`, `RUN_ID`). F2 explains why not the spelling typed.
- Exit after is 1 for every row. `--json` is "yes" where the command has the option; a command with "no" writes the
  sentence to standard error.
- Rows run in the order each check fires; the per-command order is in [section C](#c-the-mechanism).

#### `investment_analysis_engine/cli_support.py`: shared helpers

| Row | Command(s) | Option or argument | What is rejected | Sentence today | Sentence after | `parameters` | Exit today | Exit after | `--json` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| SUP-1 | `momentum`, `graham-number`, `graham-growth`, `fcf-growth` | `--details`, `--diagnostics`, `--json` | More than one of the three given | `Choose only one of --details, --diagnostics, or --json.` | unchanged | the ones given, in that order | 2 | 1 | yes |
| SUP-2 | `momentum`, `graham-number`, `graham-growth` | `TICKER`, `--ticker` | The two name different symbols | `Positional TICKER and --ticker refer to different symbols.` | unchanged | `["TICKER", "--ticker"]` | 2 | 1 | yes |
| SUP-3 | `graham-number`, `graham-growth` | `TICKER` | Omitted (optional to the parser) | `TICKER is required. Use 'ian graham-number TICKER'.` (command name interpolated) | unchanged | `["TICKER"]` | 2 | 1 | yes |
| SUP-4 | `momentum`, `graham-number`, `graham-growth`, `fcf-growth` | `TICKER` or `--ticker`, whichever was selected | Blank after trimming | `Ticker must be a non-empty symbol.` | `TICKER must be a non-empty symbol.` or `--ticker must be a non-empty symbol.` | `["TICKER"]` or `["--ticker"]` | 2 | 1 | yes |
| SUP-5 | `graham-number`, `graham-growth`, `fcf-growth`; `watchlist create`, `watchlist add-selection` for those methods | `--data-provider` | Blank after trimming | `--data-provider must be non-empty when supplied.` | unchanged | `["--data-provider"]` | 2 | 1 | direct yes; watchlist no |
| SUP-6 | the four direct commands; `watchlist create`, `watchlist add-selection` for all four methods | `--as-of` | Blank after trimming | `--as-of must be non-empty when supplied.` | unchanged | `["--as-of"]` | 2 | 1 | direct yes; watchlist no |
| SUP-7 | same as SUP-6 | `--as-of` | Not `YYYY-MM-DD` and not an ISO-8601 timestamp | `--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp.` | unchanged | `["--as-of"]` | 2 | 1 | direct yes; watchlist no |
| SUP-8 | same as SUP-6 | `--as-of` | A timestamp with no UTC offset | `Timestamp --as-of values must include an explicit timezone offset.` | unchanged | `["--as-of"]` | 2 | 1 | direct yes; watchlist no |
| SUP-9 | `graham-number`, `graham-growth`; `watchlist create`, `watchlist add-selection` for those methods | `--data-provider`, `--eps-basis`, `--eps`, `--bvps`, `--current-price`, `--expected-growth`, `--aaa-yield` | A value the Graham configuration or selection model rejects (through `config_usage_errors`; [section D](#d-the-pydantic-derived-graham-messages)) | `Invalid <option>: <pydantic message>`, or the model-level message with field names replaced by options | unchanged | the one option, or the options named in the message | 2 | 1 | direct yes; watchlist no |

#### `investment_analysis_engine/strategies/momentum/cli.py`

| Row | Command(s) | Option or argument | What is rejected | Sentence today | Sentence after | `parameters` | Exit today | Exit after | `--json` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| MOM-1 | `momentum`; `watchlist create`, `watchlist add-selection` | `--short-window` | Not positive | `Invalid momentum window: --short-window must be positive (received N).` | unchanged | `["--short-window"]` | 1 | 1 | direct yes; watchlist no |
| MOM-2 | same | `--long-window` | Not positive | `Invalid momentum window: --long-window must be positive (received N).` | unchanged | `["--long-window"]` | 1 | 1 | same |
| MOM-3 | same | `--rsi-period` | Not positive | `Invalid momentum period: --rsi-period must be positive (received N).` | unchanged | `["--rsi-period"]` | 1 | 1 | same |
| MOM-4 | same | `--short-window`, `--long-window` | Short window not smaller than long | `Invalid momentum windows: --short-window (A) must be smaller than --long-window (B).` | unchanged | `["--short-window", "--long-window"]` | 1 | 1 | same |
| MOM-5 | `momentum` | `--save-run` | Given with no explicit ticker | `--save-run requires an explicit ticker; the configured default ticker is not saved.` | unchanged | `["--save-run"]` | 2 | 1 | yes |

MOM-1 to MOM-4 exit 1 today ([B.10](SWC_CONTRACT_AND_SLICE_PLAN.md#b10-swc4a-momentum-window-failure-2026-10-06)); only `parameters` is new.

#### `investment_analysis_engine/strategies/fcf_growth/cli.py`

| Row | Command(s) | Option or argument | What is rejected | Sentence today | Sentence after | `parameters` | Exit today | Exit after | `--json` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| FCF-1 | `fcf-growth`; `watchlist create`, `watchlist add-selection` for `fcf-growth` | `--growth-years` | Not 3, 4 or 5 | `--growth-years must be 3, 4, or 5.` | unchanged | `["--growth-years"]` | 2 | 1 | direct yes; watchlist no |
| FCF-2 | same | `--forward-policy` | Not `display-only`, `confirmation` or `hard-gate` | `--forward-policy must be display-only, confirmation, or hard-gate.` | unchanged | `["--forward-policy"]` | 2 | 1 | same |
| FCF-3 | same | `--classification-basis` | Not `total-fcf` or `fcf-per-share` | `--classification-basis must be total-fcf or fcf-per-share.` | unchanged | `["--classification-basis"]` | 2 | 1 | same |
| FCF-4 | same | `--currency` | Not three letters (raised at two sites with one sentence) | `--currency must be a three-letter ISO 4217 code.` | unchanged | `["--currency"]` | 2 | 1 | same |

#### `investment_analysis_engine/strategies/graham_growth/cli.py`

| Row | Command(s) | Option or argument | What is rejected | Sentence today | Sentence after | `parameters` | Exit today | Exit after | `--json` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| GGR-1 | `watchlist create`, `watchlist add-selection` with `--analysis graham-growth` | `--expected-growth` | Omitted | hint `--expected-growth`: `Required when --analysis is graham-growth.` | `--expected-growth is required when --analysis is graham-growth.` | `["--expected-growth"]` | 2 | 1 | no |
| GGR-2 | same | `--aaa-yield` | Omitted | hint `--aaa-yield`: `Required when --analysis is graham-growth.` | `--aaa-yield is required when --analysis is graham-growth.` | `["--aaa-yield"]` | 2 | 1 | no |

The direct `graham-growth` command declares both options required to the parser, so omitting one there is a parser rejection and exits 2 (F9).

#### `investment_analysis_engine/cli_workspace.py`

| Row | Command(s) | Option or argument | What is rejected | Sentence today | Sentence after | `parameters` | Exit today | Exit after | `--json` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| WRK-1 | `watchlist create`, `watchlist add-selection`, `watchlist remove-method`, `runs list` | `--analysis` | Not a declared alias | `--analysis must be one of: momentum, graham-number, graham-growth, fcf-growth.` | unchanged | `["--analysis"]` | 2 | 1 | `runs list` yes; others no |
| WRK-2 | `watchlist create` | `--analysis`, `TICKER` | Tickers given, no `--analysis` | `--analysis is required to seed TICKER... at creation.` | unchanged | `["--analysis", "TICKER"]` | 2 | 1 | no |
| WRK-3 | `watchlist create` | `TICKER`, `--analysis` | `--analysis` given, no tickers | `At least one TICKER is required with --analysis.` | unchanged | `["TICKER", "--analysis"]` | 2 | 1 | no |
| WRK-4 | `watchlist create` | `NAME` | Blank after trimming | `1 validation error for Watchlist`, `Value error, display_name must not be blank.`, `[type=value_error, input_value={...}, input_type=dict]` and a pydantic URL (one block of text) | `NAME must not be blank.` | `["NAME"]` | 2 | 1 | no |
| WRK-5 | `watchlist create` (seed tickers, checked before the watchlist is created), `watchlist add-selection`, `watchlist remove-ticker` | `TICKER` | Any ticker blank after trimming | `ticker must not be empty.` | `TICKER must not be empty.` | `["TICKER"]` | 2 | 1 | no |
| WRK-6 | `watchlist remove-entry` | `INDEX` | Below 1 | `INDEX must be 1 or greater.` | unchanged | `["INDEX"]` | 2 | 1 | no |
| WRK-7 | `watchlist delete` | `--yes` | Not given and standard input is not interactive | hint `--yes`: `--yes is required when input is not interactive.` | unchanged | `["--yes"]` | 2 | 1 | yes |
| WRK-8 | `watchlist rename` | `NEW_NAME` | Blank after trimming | `display_name must not be blank.` | `NEW_NAME must not be blank.` | `["NEW_NAME"]` | 2 | 1 | yes |
| WRK-9 | `watchlist show` | `--group-by` | Not `ticker` or `method` | `--group-by must be 'ticker' or 'method'.` | unchanged | `["--group-by"]` | 2 | 1 | yes |
| WRK-10 | `runs list` | `--ticker` | Blank after trimming | `ticker must not be empty.` | `--ticker must not be empty.` | `["--ticker"]` | 2 | 1 | yes |
| WRK-11 | `runs list` | `--status` | Not a run outcome | `--status must be one of: completed, unavailable, not_applicable, failed.` | unchanged | `["--status"]` | 2 | 1 | yes |
| WRK-12 | `runs list` | `--refresh-id` | Not a UUID | hint `--refresh-id`: `'abc' is not a valid Analysis Run ID. Use the full ID exactly as shown by 'runs list' or 'refresh' — not a shortened or partial value.` | `--refresh-id 'abc' is not a valid Analysis Run ID. Use the full ID exactly as shown by 'runs list' or 'refresh' — not a shortened or partial value.` | `["--refresh-id"]` | 2 | 1 | yes |
| WRK-13 | `runs show` | `RUN_ID` | Not a UUID | hint `RUN_ID`: the sentence of WRK-12 | `RUN_ID 'abc' is not a valid Analysis Run ID. Use the full ID exactly as shown by 'runs list' or 'refresh' — not a shortened or partial value.` | `["RUN_ID"]` | 2 | 1 | yes |
| WRK-14 | `runs list` | `--limit` | Outside 1 to 100 | `1 validation error for RunQuery`, `limit`, `Input should be greater than or equal to 1 [type=greater_than_equal, input_value=0, input_type=int]` and a pydantic URL (less than or equal to 100 above the range) | `--limit must be between 1 and 100.` | `["--limit"]` | 2 | 1 | yes |
| WRK-15 | `runs list` | `--offset` | Below 0 | the same kind of block for `offset` | `--offset must be 0 or greater.` | `["--offset"]` | 2 | 1 | yes |
| WRK-16 | `runs show` | `--details`, `--diagnostics`, `--json` | More than one given | `Choose only one of --details, --diagnostics, or --json.` | unchanged | the ones given, in that order | 2 | 1 | yes |
| WRK-17 | `refresh` | `--workers` | Outside 1 to 4 | `workers must be between 1 and 4.` | `--workers must be between 1 and 4.` | `["--workers"]` | 2 | 1 | yes |

`WRK-14` and `WRK-15` today produce one block listing every failed field when both are wrong; after step 2 the checks run in
order and the first failing one is reported, like Momentum's windows.

#### `investment_analysis_engine/cli_health.py`, `investment_analysis_engine/cli_database.py`, `investment_analysis_engine/cli.py`

| Row | Command(s) | Option or argument | What is rejected | Sentence today | Sentence after | `parameters` | Exit today | Exit after | `--json` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| HLT-1 | `health` | `--provider` | Not `yfinance` or `sec_edgar` | hint `--provider`: `Unknown provider 'bogus'; valid providers are: yfinance, sec_edgar.` | `Unknown --provider 'bogus'; valid providers are: yfinance, sec_edgar.` | `["--provider"]` | 2 | 1 | yes |
| DB-1 | `db status`, `db upgrade` | `--database-url` | A supplied URL the settings validators reject (not SQLite, credentials, host, port or query, a file URI, a partly anchored Windows path) | `Select a valid local SQLite database URL: <validator message>` | `Select a valid local SQLite database URL for --database-url: <validator message>` | `["--database-url"]` | 2 | 1 | yes |
| DB-2 | `db status`, `db upgrade` | `--database-url` | The target is private memory and the option was supplied | `Database maintenance requires a file-backed target; private memory is not supported.` | `Database maintenance requires a file-backed target for --database-url; private memory is not supported.` | `["--database-url"]` | 2 | 1 | yes |
| DB-3 | `db status`, `db upgrade` | none (the configured `database_url` setting) | The target is private memory and the option was not supplied | the sentence of `DB-2` | unchanged; reported as `configuration_error`, not `invalid_parameter` | null | 2 | 1 | yes |
| EVL-1 | `evaluate` | `--report` | A path Windows would only partly anchor | hint `--report`: `--report path '/e/x/y.json' has a root but no drive letter, ... 'cygpath -m <path>' prints the Windows form.` | unchanged | `["--report"]` | 2 | 1 | no |
| EVL-2 | `evaluate` | `--case` | Not a Golden case ID | hint `--case`: `Unknown Golden case ID 'ZZZ'. Available IDs: MOM-01, ...` | `Unknown Golden case ID 'ZZZ' for --case. Available IDs: MOM-01, ...` | `["--case"]` | 2 | 1 | no |
| EVL-3 | `evaluate` | `--mode` | An Ollama-only option given while the mode is deterministic | hint `--mode`: `Ollama options require --mode ollama.` | unchanged | `["--mode"]` | 2 | 1 | no |
| EVL-4 | `evaluate` | `--report` | The file exists and `--overwrite` is absent | hint `--report`: `Report already exists: <path>. Use --overwrite to replace it.` | `--report target already exists: <path>. Use --overwrite to replace it.` | `["--report"]` | 2 | 1 | no |

#### Rows confirmed by running

On 2026-10-11 I invoked each of these through Typer's `CliRunner` (the runner the CLI tests use), against a disposable migrated
database arranged as `tests/_cli_helpers.py` does, and read the exit code and both streams. Every sentence and exit code in the
"today" columns of the rows below is as printed.

- Every group: all of `SUP-1` to `SUP-9` (`SUP-1` on `momentum` and `graham-number`, `SUP-3` on `graham-number`, `SUP-5` on
  `graham-number` and `fcf-growth --json`, `SUP-7` on `momentum --json`, `graham-number` and `watchlist create`), `MOM-1`
  (`momentum --json`: envelope on standard output, exit 1; `watchlist create`: sentence, exit 1), `MOM-4` (text, exit 1) and
  `MOM-5`, `FCF-1` to `FCF-4` (the direct command; `FCF-4` also with `--json`) and `FCF-1`, `FCF-4` through `watchlist create`,
  `GGR-1`, `GGR-2`, every row `WRK-1` to `WRK-17` (`WRK-1` on all four commands; `WRK-5` on all three; `WRK-7`, `WRK-8`, `WRK-9`,
  `WRK-13` and `WRK-17` with and without `--json`, which wrote nothing on standard output), `HLT-1` (with and without `--json`),
  `DB-1` (two URLs, one with `--json`), `DB-2`, `EVL-1` to `EVL-4`.
- Not run: `MOM-2`, `MOM-3` (the same function as `MOM-1`), and the `graham-growth` forms of `SUP-2` to `SUP-4`, `FCF-2` and `FCF-3`
  through `watchlist create` (same helpers).
- A run I did not intend: my first batch split a quoted blank argument, so one `momentum` invocation ran past the checks and sent
  Yahoo Finance's single provider-check request. It changed nothing in the repository.

### B. The `ValueError` audit

Decision 6 covers the places that catch a `ValueError` from the workspace layer and re-raise it as a usage error. There are seven
(`investment_analysis_engine/cli_workspace.py`). For each, the exceptions the guarded call can raise were read from the repository and model code, and
the two surprises were reproduced by running.

| Site | Guarded call | Exceptions it can catch and where raised | Disposition |
| :--- | :--- | :--- | :--- |
| `watchlist create`, around `repository.create` | `SQLiteWatchlistRepository.create` | Blank name: `pydantic.ValidationError` (a `ValueError`) from `Watchlist._validate_watchlist` in `investment_analysis_engine/workspace/runs.py`, whose text is the pydantic block of `WRK-4`. `WatchlistConflictError` is caught first and already reported as `watchlist_name_conflict`. `_utc` raises `ValueError` only for a naive clock; the clock is `utc_now`. | The blank name is an explicit `NAME` check, `WRK-4`, immediately before the call. The rest cannot occur. |
| `watchlist create`, around `repository.add_entries` | `add_entries` on the watchlist just created | `normalize_ticker`: blank ticker. `WatchlistNotFoundError` and `StoredSelectionError` (from `_load`) cannot occur on rows written a moment earlier. `ValueError` from a corrupt stored row (`UUID`, `fromisoformat`, a `Watchlist` validation) cannot occur on a fresh row. | The blank ticker is an explicit `TICKER` check, `WRK-5`, made for every seed ticker before the watchlist is created (F3, ruled), so a blank ticker leaves nothing behind. Anything else is reported by the generic path below. |
| `watchlist add-selection` | `add_entries` on an existing watchlist | Blank ticker (`normalize_ticker`). `WatchlistNotFoundError`, caught first, `watchlist_not_found`. **`StoredSelectionError` from `_load` when any existing entry is unreadable: reproduced, it exits 2 today as a usage error whose text ends "Remove it with: ian watchlist remove-entry ...".** The insert rolls back with it. | The blank ticker is an explicit `WRK-5` check before the call. `StoredSelectionError` is reported under `stored_selection_unreadable`, exit 1, with its own sentence unchanged, the way every other command that reads the watchlist already reports it. |
| `watchlist remove-ticker` | `remove_entries_for_ticker` | Blank ticker only; the method decodes no entry. `WatchlistNotFoundError` is caught first. | Explicit `WRK-5` check before the call. |
| `watchlist rename` | `repository.rename` | Blank new name: a plain `ValueError("display_name must not be blank.")`. `WatchlistNotFoundError` and `WatchlistConflictError` are caught first. | Explicit `WRK-8` check before the call. |
| `runs list` | `RunQuery(...)` and the argument conversions | `normalize_ticker` (blank `--ticker`), `RunQuery` field bounds for `limit` and `offset` (a `ValidationError`). The alias, status and refresh-ID conversions raise `typer.BadParameter`, which is not a `ValueError` and passes through unchanged today. | Explicit checks `WRK-10`, `WRK-14`, `WRK-15`, in the order the arguments are evaluated today, with `WRK-1`, `WRK-11` and `WRK-12` between them. |
| `refresh` | `RefreshPolicy(workers=...)` | The one `ValueError` in `RefreshPolicy.__post_init__`: the worker range. | Explicit `WRK-17` check. |

The residual: an exception that none of the explicit checks names (a corrupt stored watchlist row is the only way to reach a
`ValueError` here) is not caught as a usage error. `_workspace_database` takes the command as typed after `ian` and catches every
exception raised inside its block. An exception that declares its own code, such as `StoredSelectionError`, keeps its own sentence. Any
other exception, a `pydantic.ValidationError` included, is an `execution_error` with the fixed sentence `<command> failed unexpectedly.`
(for example `watchlist add-selection failed unexpectedly.`); its detail goes to the log with its traceback, so no library text
reaches the user. `typer.Exit` and `typer.Abort` pass through. `invalid_input` is not used there. Nothing in the tests or the code can
produce a corrupt row, so step 2 injects a real `ValidationError` and a plain `ValueError` and pins the code, the sentence and the
absence of `input_value`, `validation error for` and `errors.pydantic.dev`.

`runs show` has its own read failure: the run repository's `get` raises a plain `ValueError` when the stored envelope fails validation
and when the envelope disagrees with its own row. Both report `invalid_stored_run` with the one sentence `Analysis Run <full run ID>
could not be read: its stored record is malformed or does not match its summary.`; the exception detail goes to the log with its
traceback.

The other catch-and-re-raise sites are not workspace-layer sites. Each guards one standard-library or model call whose only
`ValueError` is the check itself, so each stays an explicit check at its own position:

| Site | Guarded call | Disposition |
| :--- | :--- | :--- |
| `_parse_as_of` | `date.fromisoformat`, `datetime.fromisoformat` | `SUP-7` |
| `_parse_status` | `RunOutcome(value)` | `WRK-11` |
| `_parse_run_id` | `UUID(value)` | `WRK-12`, `WRK-13` |
| `_fcf_forward_policy`, `_fcf_classification_basis` | an enum constructor | `FCF-2`, `FCF-3` |
| `evaluate` `--report` | `require_anchored_path` | `EVL-1` |
| `_run`, first handler | `ProjectSettings(...)` raising `ValidationError` | `DB-1`. Reachable only when `--database-url` is supplied. |
| `_run`, second handler | `SQLiteDatabase(selected)` raising `ValueError` | **Unreachable**: the constructor calls `make_url` on a URL the settings model has already validated and raises no `ValueError`. Step 2 removes the handler and the check it implies. |

### C. The mechanism

One path, in `investment_analysis_engine/cli_support.py`, reports a check raised before or inside a command's failure handling. A check raises
`InvalidParameterError`; it never writes output.

1. **Raise.** `InvalidParameterError(message, *, parameters)` takes the names as a required keyword argument and keeps them
   as a tuple attribute. It stays a `ValueError` subtype, and the classifier already maps it to `invalid_parameter`.
2. **Carry.** `parameters` travels as an attribute of the exception, read the way `provider_failure_of_exception` reads `kind`: a
   function in `investment_analysis_engine/core/failure_classification.py` returns `getattr(exception, "parameters", None)` when it is a tuple of strings
   and names no exception type. `failure_envelope` (in `investment_analysis_engine/reporting/failure_envelope.py`) passes it to the model when the code is
   `invalid_parameter`. The model field is `parameters: tuple[str, ...] | None`; a validator requires a non-empty tuple exactly
   when `reason_code` is `invalid_parameter` and refuses it otherwise. The raising code, which already owns the sentence,
   owns the names, so generic code holds no per-strategy entry.
3. **Direct commands.** The body of each direct command, including the ticker and output-flag checks that run first today,
   runs inside one `execution_errors` block. `execution_errors` takes the raw `json_output` flag and yields a small mutable
   `FailureScope` holding the `ticker` and `mode` that the failure document needs. The scope starts with no ticker and a mode of
   `JSON` when `--json` was given and `CONCISE` otherwise; the command sets `scope.ticker` and `scope.mode` as soon as
   `_resolve_ticker` and `_presentation_mode` succeed. The case where the output-flag check itself fails therefore reports in `JSON`
   whenever `--json` was among the flags, with `ticker` set when it had resolved; with `--details --diagnostics` and no `--json` the
   sentence goes to standard error. The Graham commands keep their two nested blocks, and `FCF`'s combined `with` becomes a nested
   one so the checks still precede opening the cache.
4. **Every other command.** A second context manager, `parameter_failures(json_output=...)`, catches only `InvalidParameterError`
   and reports it through the one writer. `report_failure(envelope, *, json_output)`, which replaces `cli_workspace._report`, writes the
   envelope to standard output for `--json` and the sentence to standard error otherwise, then exits 1. The watchlist, `runs`, `refresh`,
   `health`, `db` and `evaluate` commands enter it around their checks with their own `json_output` (`False` for a command with no
   `--json`, which gives decision 4). `typer.Exit` passes through both managers.
5. **What exits 2.** Nothing the command's code raises. Click raises its own `UsageError` before the command function runs, so
   neither manager sees it; step 2 removes the `UsageError` arm of `execution_errors`, which becomes dead.
6. **Order.** Each check is raised at the line where it is raised today; the explicit workspace checks of section B sit
   immediately before the repository call that raised them. No check moves relative to another check or to a resource.

Order of the checks within each command, unchanged:

| Command | Order |
| :--- | :--- |
| `momentum` | `SUP-2`, `SUP-4`, `SUP-1`, `MOM-1`, `MOM-2`, `MOM-3`, `MOM-4`, `SUP-6`, `SUP-7`, `SUP-8`, `MOM-5` |
| `graham-number`, `graham-growth` | `SUP-2`, `SUP-3`, `SUP-4`, `SUP-1`, `SUP-6`, `SUP-7`, `SUP-8`, `SUP-5`, `SUP-9` |
| `fcf-growth` | `SUP-4`, `SUP-1`, `FCF-1`, `SUP-6`, `SUP-7`, `SUP-8`, `SUP-5`, `FCF-4`, `FCF-3`, `FCF-2` |
| selection builders | Momentum: `MOM-1` to `MOM-4`, then `SUP-6` to `SUP-8`. Graham Number: `SUP-6` to `SUP-8`, `SUP-5`, `SUP-9`. Graham Growth: `SUP-6` to `SUP-8`, `SUP-5`, `GGR-1`, `GGR-2`, `SUP-9`. FCF Growth: `SUP-6` to `SUP-8`, `SUP-5`, `FCF-4`, `FCF-1`, `FCF-3`, `FCF-2`. |
| `watchlist create` | `WRK-2`, `WRK-3`, `WRK-1`, the builder, then the database, `WRK-4`, `WRK-5` (every seed ticker), then the create |
| `watchlist add-selection` | `WRK-1`, the builder, then the database, `WRK-5` |
| `watchlist remove-ticker` | the database, then `WRK-5` |
| `watchlist rename` | the database, then `WRK-8`, then not-found and name conflict |
| `watchlist remove-entry`, `remove-method`, `delete`, `show`, `refresh` | `WRK-6`, `WRK-1`, `WRK-7`, `WRK-9`, `WRK-17` respectively, before the database |
| `runs list` | `WRK-10`, `WRK-1`, `WRK-11`, `WRK-12`, `WRK-14`, `WRK-15`, then the database |
| `runs show` | `WRK-16`, `WRK-13`, then the database |
| `db status`, `db upgrade` | `DB-1`, then `DB-2` or `DB-3` |
| `evaluate` | `EVL-1`, `EVL-2`, `EVL-3`, `EVL-4` |

### D. The pydantic-derived Graham messages

`config_usage_errors` takes the first error of a `ValidationError` with `include_input=False, include_url=False`. A field-level
error becomes `Invalid <option>: <message>` through a field-to-option map; a model-level error has its field names replaced by option
names. The `parameters` value is the option from the map for a field-level error, and for a model-level error the options whose field
name appeared in the message, in map order. Every message below is reached by running or by reading the validators; none changes.

| Source | Reached from | Sentence | `parameters` |
| :--- | :--- | :--- | :--- |
| `eps_basis` outside the declared literal | direct commands and builders; the allowed values differ by model | `Invalid --eps-basis: Input should be 'three_year_average' or 'ttm'` (Graham Number direct); `'three_year_average'` (Number builder); `'three_year_average', 'ttm' or 'fiscal_year'` (Growth direct); `'three_year_average' or 'fiscal_year'` (Growth builder) | `["--eps-basis"]` |
| Model-level SEC rule in `validate_method` | direct commands, `--eps-basis ttm` with the default provider | `SEC EDGAR requires --eps-basis to be one of (three_year_average) (received 'ttm').` (Growth lists `fiscal_year, three_year_average`) | `["--eps-basis"]` |
| `security_provider_id` not a supported provider | builders only (the direct config accepts any provider id) | `Invalid --data-provider: Unsupported security provider 'bogus'; supported provider is 'sec_edgar'.` (F10b: the `Value error, ` prefix is stripped) | `["--data-provider"]` |
| Non-finite `--eps`, `--bvps`, `--current-price`, `--expected-growth`, `--aaa-yield` | builders only; the direct configurations have no finiteness check (F10) | `Invalid --eps: Financial override must be a finite number.` (F10b: prefix stripped) | the option |
| Blank provider id, `as_of`, unknown field, strict `use_cache`, `quote_provider_id` | not reachable: `SUP-5` rejects a blank provider first, the builders pass an already validated `as_of`, and no option feeds the others | none | none |

Can a message expose an input value it should not? No message does.

- The two ways pydantic prints an input, `input_value`/`input_type` and its documentation URL, are excluded by the call's flags.
  The existing test `test_usage_validation_precedes_resources` asserts neither `input_value` nor `validation error for` appears on the direct path.
- The only values a message echoes are the ones the user typed on that option: the provider id (lower-cased and trimmed) and the
  EPS basis. A default basis cannot reach the SEC rule, because it is accepted. This is the same disclosure as Momentum's
  `(received N)`, and neither option carries a credential.
- The one path that could print an input is a `ValidationError` raised inside another model's validator, whose text pydantic nests. The
  Number and Growth selections build their own configuration inside a model validator, so the path exists, but a selection has
  already restricted the provider and basis to the sets the configuration accepts, so it is not reachable today.
- Step 2 extends that test to the builders, and adds one that fails if any mapped sentence contains `input_value`,
  `validation error for` or `errors.pydantic.dev`.
- `config_usage_errors` has a fallback option name, `Graham options`, for a field absent from the map. No reachable field is absent, so step 2 replaces the fallback with a strict lookup that fails loudly (F10a).

### E. File scope, tests and documents for step 2

Source files:

- `investment_analysis_engine/core/operator_errors.py`: `InvalidParameterError` takes `parameters`.
- `investment_analysis_engine/core/failure_classification.py`: the function that reads `parameters` from an exception.
- `investment_analysis_engine/reporting/documents/failure.py`: the `parameters` field and its rule; `schema_version` 10.
- `investment_analysis_engine/reporting/failure_envelope.py`: pass `parameters` to the model.
- `investment_analysis_engine/cli_support.py`: `execution_errors` (`json_output`, `FailureScope`), `parameter_failures`, `report_failure`, every `raise` in the
  helpers, `config_usage_errors`, removal of the `UsageError` arm and import.
- `investment_analysis_engine/cli_workspace.py`: all 16 raise sites, the explicit checks of section B, `_report` replaced by `report_failure`, the
  `except InvalidParameterError` in `_build_selection` removed, `runs show` using the shared mode helper, the catch-all
  in `_workspace_database`, the `runs show` read-failure sentence, docstrings that say "usage error".
- `investment_analysis_engine/cli.py` (`evaluate`), `investment_analysis_engine/cli_health.py`, `investment_analysis_engine/cli_database.py`.
- `investment_analysis_engine/strategies/momentum/cli.py`, `fcf_growth/cli.py`, `graham_growth/cli.py`, `graham_number/cli.py`.
- `investment_analysis_engine/workspace/refresh.py` and `investment_analysis_engine/workspace/runs.py`: the worker range and the `limit` bounds become named constants that the
  model and the CLI check share. These two files are outside the CLI modules and the change is a constant extraction with no behavior
  change; if the project owner prefers, the constants live in the CLI and are duplicated.
- `schemas/failure.schema.json`, regenerated by `scripts/generate_schemas.py`.

Tests to add:

- A source scan that fails when any file under `investment_analysis_engine/` raises `typer.BadParameter` (an AST scan, with a negative control on a temporary file).
- A table-driven test over section A: each row through the CLI runner in text mode and, where the command has `--json`, in `--json` mode.
- Parser controls: an unknown option, a missing argument, a wrong type and an out-of-choice value still exit 2 with text for every family.
- Order tests: one command line violating two checks per command of the order table in section C.
- The output-flag failure with `--json` (envelope) and without (sentence), including with a blank ticker.
- The `parameters`/sentence invariant over every row; the model tests for `parameters` (null unless `invalid_parameter`, non-empty when set).
- The catch-all and `runs show` read-failure tests of section B, the unreadable-entry `add-selection` test, and a test that the watchlist does not exist after a blank seed ticker fails (F3).
- The Graham message tests of section D.

Existing tests that change (command-level checks assert exit 1 and the new sentence; parser rejections keep exit 2):

- `tests/test_cli.py`: the exclusive-flags and conflicting-ticker tests; its option-rejection tests at lines 611 to 644 are parser rejections and stay.
- `tests/test_cli_database.py` (three tests), `tests/test_cli_health.py` (two), `tests/test_cli_refresh.py` (one), `tests/test_cli_save_run.py` (one),
  `tests/test_graham_growth_default_policy.py` (one), `tests/test_cli_fcf_earnings_growth.py` (three), `tests/test_cli_failure_envelope.py`
  (the `--as-of` test and `_ENVELOPE_KEYS`, which gains `parameters`; `schema_version` 10).
- `tests/test_cli_graham_commands.py`: `test_usage_validation_precedes_resources`, `test_missing_ticker_names_the_invoking_command`, and the
  `typer.BadParameter` parameter of `test_command_exception_closes_cache_and_preserves_exit`.
- `tests/test_cli_support.py`: the pass-through test for `BadParameter` and `UsageError`, and the tests that expect `typer.BadParameter` from the helpers.
- `tests/test_cli_workspace.py`: about 25 assertions of exit 2 for rows `WRK-1` to `WRK-17`; the "Missing argument" and "No such command/option" assertions stay.
- `tests/evaluation/test_cli.py`: four assertions (`EVL-1` to `EVL-4`).
- `tests/reporting/test_failure_envelope.py` and `tests/_failure_code_table.py`, which construct `InvalidParameterError` without names.
- `tests/test_strategy_import_layering.py`, only if a new import edge needs an entry.
- Stored expected output: none. `tests/expected_output/` holds no failure document and no usage error; `--help` output is unchanged. Step 2 confirms by running the stored-output tests.

Documents:

- `SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md` §13.2 (the shape table gains `parameters`), §13.3 (the `invalid_parameter` row, the "exactly three" section replaced by a pointer to section A of this plan), §13.4 (the output changes as new rows) and the one-sentence description of exit 2 wherever the design repeats it. The design's §13.3 is not edited in step 1.
- `SWC_CONTRACT_AND_SLICE_PLAN.md`: the SWC.4d row to `Complete` and the next row to `Next`, when step 2 completes.
- `docs/user/USAGE.md` (the failure-document paragraph and the `health` paragraph), `docs/user/WORKSPACE.md` (the exit-code table row for `2` and the rows that say usage error), `docs/user/DATABASE.md` (the exit-code sentence and the sentence about parser-level errors).
- Schemas: `schemas/failure.schema.json`; no other schema changes.

### F. Findings that do not fit the decisions

Each is for the project owner. I resolved none.

1. **Three sentences are not a prefix change (`WRK-4`, `WRK-14`, `WRK-15`).** Today they are a pydantic block with an `input_value` and a URL, which names no option or argument and was
   written by nobody. I read decision 5's "every sentence names its option or argument" as covering them, so section A proposes `NAME must not be blank.`, `--limit must be
   between 1 and 100.` and `--offset must be 0 or greater.`. This is the nearest case to the stop condition "a sentence would have to change for a reason other
   than decision 5". **Recommendation:** approve the three wordings. If the reading is wrong, hold these three rows.
2. **`parameters` cannot be "exactly as typed".** Typer gives the command the value, not the spelling used, so `-g` and `--expected-growth-rate` are indistinguishable from
   `--expected-growth`. **Recommendation:** use the declared primary long spelling for an option and the upper-case name the sentences already use for an argument (rule R in section A). Short and alias spellings never appear.
3. **`watchlist create` with a blank seed ticker leaves an empty watchlist behind.** Reproduced: it exits 2 today but the watchlist was already created, because the ticker is checked after the create
   (`WRK-5`). Keeping the order keeps that. After this slice it exits 1 and the same watchlist exists, which reads as "nothing happened". **Recommendation:** check the seed tickers before the create. The only
   order change is for a command line that has both an existing watchlist name and a blank ticker, where both failures are true; the plan keeps today's order until you choose.
4. **An output change the decisions did not list.** `watchlist add-selection` on a watchlist holding an unreadable entry exits 2 as a usage error today (section B) and will exit 1 as
   `stored_selection_unreadable`. It is the disposition decision 6 asks for, but it is a new code on a command the decisions name only through its checks. **Recommendation:** accept and list it in B.14's output-change table.
5. **Three document shapes for `db` and `health` under `--json`.** `db` writes a `DatabaseMaintenanceReport` for a readiness failure and, after this slice, a `FailureEnvelope` for a rejected `--database-url`; `health` writes a `ProviderHealthDocument` and now an envelope for a rejected `--provider`.
   A consumer tells them apart by `result` and `command`. **Recommendation:** accept, per decision 1, and say so in `DATABASE.md` and `USAGE.md`; the alternative is to put `parameters` on the sibling reports, which decision 7 does not ask for.
6. **A private-memory target is not always a `--database-url` problem (`DB-2`).** The check also fires when the memory URL comes from the settings, where no parameter is at fault. **Recommendation:** `invalid_parameter` with `["--database-url"]` when the option was supplied, and `configuration_error` with the existing sentence when it was not. Decision 3 names `invalid_parameter` for all of these, so this needs your approval.
7. **One option, two codes.** An unsupported `--data-provider` is `configuration_error` (exit 1, an envelope) on the direct Graham commands, because the permissive configuration accepts any provider id and the resolver builder rejects it, and `invalid_parameter` on `watchlist create` and `add-selection`, because the strict selection rejects it. **Recommendation:** leave both; moving the direct command's failure to `invalid_parameter` would change an existing code's meaning.
8. **The stability rule holds with wording changes (5.3).** `EVL-4` and `WRK-7` depend on a file and a terminal, not on the value alone, so "will always fail" in §13.3 becomes "fails as given". No decision is needed unless you want those two rows kept out of `invalid_parameter`.
9. **The same mistake exits differently by where it is made.** A missing `--expected-growth` or `--aaa-yield` exits 2 on `graham-growth` (the parser requires it) and 1 on `watchlist create` (`GGR-1`, `GGR-2`); a missing ticker exits 2 on `fcf-growth` and 1 on `graham-number` (`SUP-3`). Decision 3 rules out converting a check to a parser constraint, so this follows from it. **Recommendation:** accept, and document "exit 2 means the parser rejected the command line" in `USAGE.md` and `WORKSPACE.md`.
10. **Loose ends in `config_usage_errors` (section D).** (a) The fallback name `Graham options` is unreachable and would put a made-up name in `parameters`; recommend a strict lookup so an unmapped field fails loudly. (b) Three reachable sentences carry pydantic's `Value error, ` prefix on the field-level branch only; decision 5 keeps them, recommend stripping it as the model-level branch does. (c) The direct Graham configurations accept `--eps nan` (no finiteness check, by reading the models; not run) while the builders reject it. That is a correctness item outside this slice; recommend a separate note under the existing-strategy correctness process.

### Rulings on the findings (project owner, before step 2)

| Finding | Ruling |
| :--- | :--- |
| F1 | Approved: `NAME must not be blank.`, `--limit must be between 1 and 100.`, `--offset must be 0 or greater.` |
| F2 | Approved: `parameters` holds each option's declared primary long spelling and each argument's upper-case name as the sentences use it. This replaces "exactly as typed" in decision 7. |
| F3 | Fix in this slice: `watchlist create` checks every seed ticker before it creates the watchlist. The accepted order change: a name that already exists together with a blank ticker now reports the blank ticker. A test checks the watchlist does not exist after the failure. |
| F4 | Accepted; listed with the output changes. |
| F5 | Accepted; stated in `DATABASE.md` and `USAGE.md`. |
| F6 | Approved: `invalid_parameter` with `["--database-url"]` when the option was supplied (`DB-2`); `configuration_error` with the existing sentence when the target came from the settings (`DB-3`). |
| F7 | **Moved to SWC.4e.** The direct Graham commands keep `configuration_error` from `build_graham_resolver` for an unsupported `--data-provider`, and the watchlist builders keep `invalid_parameter`; the two codes remain until SWC.4e removes the permissive configuration the direct commands use so tests can inject a synthetic provider ([B.15](SWC_CONTRACT_AND_SLICE_PLAN.md#b15-swc4e-the-direct-graham-commands-reject-an-unsupported-provider-2026-10-11)). Nothing in SWC.4d touches that configuration or the tests that use it. |
| F8, F9 | Accepted; the documents say exit 2 means the parser rejected the command line. |
| F10a, F10b | Approved: a strict lookup in `config_usage_errors`; the `Value error, ` prefix is stripped. |
| F10c | Not fixed here. Reproduced through the CLI test runner with no network in step 2; if a non-finite override is accepted a GitHub issue is opened and referenced from the existing-strategy correctness plan. |
| Scope | Editing `investment_analysis_engine/workspace/refresh.py` and `investment_analysis_engine/workspace/runs.py` is approved, only to define the worker and limit bounds once. |

### G. Differences between this plan and the implementation

Found while implementing step 2; each is small and none changes a row of section A.

- **Create order.** The plan's order table put `WRK-5` before `WRK-4`; the implementation checks the name first, then every seed ticker, then creates, so only the accepted change (a taken name with a blank ticker reports the blank ticker) differs from today.
- **`execution_errors` signature.** It gains `json_output` and yields the `FailureScope`, and keeps its `mode` parameter as the scope's initial mode instead of replacing it.
- **Moved into the handler.** The FCF command's policy and configuration are now built inside its handler, so a `ValueError` from them is reported as a failure; before it would have escaped as a traceback.
- **Workspace catch-all.** `_workspace_database` reports an exception that declares its own code (an `InvalidParameterError` raised inside the block included) under that code and sentence, and any other exception as an `execution_error` (see the next bullets), and the pre-check regions of the commands use `parameter_failures`. `_report` is replaced by `report_failure` in `investment_analysis_engine/cli_support.py`.
- **Database commands.** The target is opened by a new `_open_database` helper that holds `DB-1` to `DB-3`; the unreachable second `ValueError` handler is removed.
- **Strict lookup.** `config_usage_errors` re-raises the original `ValidationError` when a model-level message names no mapped field, so nothing is reported under an invented option.
- **Constants.** `MIN_WORKERS` and `MAX_WORKERS` in `investment_analysis_engine/workspace/refresh.py` and `RUN_QUERY_MIN_LIMIT` and `RUN_QUERY_MAX_LIMIT` in `investment_analysis_engine/workspace/runs.py`, as approved.
- **A test seam.** The logging driver's "crash" scenario patched `_presentation_mode`, which now runs inside the handler; it patches `provider_check_choice`, which still runs before it.
- **`runs show`.** A stored run that cannot be read reports one sentence, `Analysis Run <full run ID> could not be read: its stored record is malformed or does not match its summary.`, under `invalid_stored_run`; the validation text goes to the log. This resolves issue 113 ([B.16](SWC_CONTRACT_AND_SLICE_PLAN.md#b16-swc4d-follow-up-the-workspace-catch-all-runs-show-and-refresh-2026-10-12)).
- **The workspace catch-all.** `_workspace_database` takes the command as typed after `ian` and catches every exception, not only `ValueError`. One that declares its own `reason_code` keeps its sentence; any other is an `execution_error` with `<command> failed unexpectedly.` and its detail in the log; `typer.Exit` and `typer.Abort` pass through. This replaced the `invalid_input` the plan first named for a residual `ValueError`; section B now states the catch-all. No sentence of section A changes.
- **`evaluate`.** It keeps its raw error text (`Evaluation failed: ...`) by decision: it is a developer command whose readers need the detail.
- **Refresh job text.** The `error` field of a failed refresh job still carries the exception's own text; that is [SWC.4f](SWC_CONTRACT_AND_SLICE_PLAN.md#swc4f--one-failure-message-rule-for-the-direct-commands-and-refresh).
- **F7 and F10c.** F7 moved to SWC.4e ([B.15](SWC_CONTRACT_AND_SLICE_PLAN.md#b15-swc4e-the-direct-graham-commands-reject-an-unsupported-provider-2026-10-11)); F10c is [ESC-30](../existing-strategy-correctness/ESC_A_DEFECT_LEDGER.md#esc-30--the-direct-graham-commands-accept-a-non-finite-override-that-the-watchlist-path-rejects), issue 124.

## Appendix A: Decision record

The eight decisions (with the rulings above, which supersede the plan where they differ) the project owner approved for this slice are recorded verbatim in
[B.14](SWC_CONTRACT_AND_SLICE_PLAN.md#b14-swc4d-command-validation-failures-2026-10-11) and are not reopened here. Where this
plan applies each:

| Decision | Subject | Applied in |
| :--- | :--- | :--- |
| 1 | Every check a command raises itself moves into the envelope | [Section A](#a-the-check-table), 45 rows |
| 2 | A test fails if any file under `investment_analysis_engine/` raises `typer.BadParameter` | [Section E](#e-file-scope-tests-and-documents-for-step-2), first new test |
| 3 | Exit 1 with `invalid_parameter`; exit 2 means the parser rejected the command line | [Section C](#c-the-mechanism) item 5; [5.3](#53-invalid_parameter-under-the-stability-rule) |
| 4 | A command with no `--json` writes the sentence to standard error and exits 1 | [Section C](#c-the-mechanism) item 4 |
| 5 | Keep each sentence; reword only to keep an option name; name the option; report, do not instruct | [Section A](#a-the-check-table), rule R; F1 |
| 6 | The caught `ValueError` sites are not relabelled wholesale | [Section B](#b-the-valueerror-audit) |
| 7 | `parameters` on the envelope; failure schema version bumped | [Section C](#c-the-mechanism) item 2; [Section E](#e-file-scope-tests-and-documents-for-step-2) |
| 8 | Two steps on one branch; this step writes the plan and stops | [Step 1](#step-1--the-slice-plan) |
