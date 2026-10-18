# Usage Guide

This guide covers the common ways to use Investment Analysis Engine after installation. Strategy-specific formulas, assumptions, and limitations live in the individual [Analysis Strategy Guides](strategies/README.md).

## The basic command shape

Commands are run from the Investment Analysis Engine installation folder:

```text
uv run ian ANALYSIS [arguments] [options]
```

An [analysis strategy](GLOSSARY.md#analysis-strategy) is a deterministic analytical capability with its own inputs, methods, and result semantics. A [method](GLOSSARY.md#method) is a particular calculation within a strategy when that strategy offers more than one approach.

See all available commands:

```bash
uv run ian --help
```

See help for a strategy:

<!-- BEGIN GENERATED strategy-help-commands: written by scripts/generate_strategy_docs.py; generated, do not edit by hand. -->
```bash
uv run ian momentum --help
uv run ian graham-number --help
uv run ian graham-growth --help
uv run ian fcf-growth --help
```
<!-- END GENERATED strategy-help-commands -->

Technical operators can also run the versioned Golden Suite with `uv run ian evaluate --help`. See [Golden Suite evaluation](#golden-suite-evaluation).

## Orchestration reliability limits

Agent orchestration is bounded and returns a terminal diagnostic instead of
letting a reliability limit escape as an unhandled error. The diagnostic names
the stable reason and the run ID; command-line consumers return a nonzero exit
status so automation can detect the failure.

The defaults are:

| Setting | Default |
|---|---:|
| `max_steps` | 10 |
| `max_transient_retries` | 3 |
| `max_consecutive_schema_violations` | 4 |
| `overall_timeout_seconds` | 300 |
| `step_timeout_seconds` | 180 |
| `llm_call_timeout_seconds` | 120 |
| `tool_call_timeout_seconds` | 60 |
| `recent_diagnostic_events` | 5 |

These values are fields below the `reliability_limits` application setting.
They can be changed without editing code through the existing nested settings
environment convention, for example
`IAN_RELIABILITY_LIMITS__OVERALL_TIMEOUT_SECONDS=240`. An explicitly constructed
`OrchestratorConfig` can instead supply one complete `ReliabilityLimits` value
for a particular run.

Timeouts cooperatively cancel asynchronous calls. Synchronous tool handlers are
moved off the event-loop thread, but Python cannot safely terminate arbitrary
thread work. If such a handler times out, orchestration stops awaiting it and
reports that cancellation was not confirmed; the handler remains responsible
for lower-level I/O timeouts and idempotent side effects.

## Available analysis strategies

Browse the [Analysis Strategy Guides](strategies/README.md) for available strategies, methods, data sources, and limitations. Use `uv run ian --help` for the commands installed in your version. The examples below illustrate common invocation patterns; they are not an exhaustive strategy inventory.

## Graham analysis

Run the Graham Number earnings-and-book-value screen:

```bash
uv run ian graham-number KO
```

Select the separate Graham Growth Value method explicitly:

```bash
uv run ian graham-growth KO \
    --expected-growth 5 \
    --aaa-yield 4.5
```

The two strategies use different values and have different interpretations. See the [Graham Number](strategies/GRAHAM_NUMBER.md) and [Graham Growth Value](strategies/GRAHAM_GROWTH.md) guides.

### Migrating existing Graham commands

The combined `graham` command and its `--method` / `-m` selector have been removed.
Use the method-specific command; removed invocations return a usage error.

| Previous invocation | Replacement |
| :--- | :--- |
| `ian graham KO` | `ian graham-number KO` |
| `ian graham KO --method number --bvps 20` | `ian graham-number KO --bvps 20` |
| `ian graham KO --method growth --expected-growth 5 --aaa-yield 4.5` | `ian graham-growth KO --expected-growth 5 --aaa-yield 4.5` |

Both commands accept positional `TICKER` or `--ticker` / `-t`, `--as-of`,
`--data-provider`, `--no-cache`, `--eps` / `-e`,
`--current-price` / `-p`, and one of `--details`, `--diagnostics`, or `--json`.
Only `graham-number` accepts `--bvps`. Only `graham-growth` accepts `--eps-basis`
and requires both
`--expected-growth` (aliases `--expected-growth-rate` / `-g`) and
`--aaa-yield` (aliases `--current-aaa-yield` / `-y`). Other applicable flags
and their financial meanings are unchanged.

## Momentum analysis

```bash
uv run ian momentum AAPL
```

With custom moving-average windows:

```bash
uv run ian momentum AAPL \
    --short-window 10 \
    --long-window 30
```

With a point-in-time boundary, bypassing the historical price cache:

```bash
uv run ian momentum AAPL --as-of 2025-12-31 --no-cache
```

See the [Momentum Analysis Strategy Guide](strategies/MOMENTUM.md).

## Free Cash Flow & Earnings Growth analysis

```bash
uv run ian fcf-growth MSFT
```

The default command selects the longest usable contiguous span—5, 4, then 3 elapsed years—and classifies growth using total-company FCF and diluted EPS. Both total-company and per-diluted-share FCF growth remain visible.

Request an exact historical span or select the per-share classification basis:

```bash
uv run ian fcf-growth MSFT --growth-years 5
uv run ian fcf-growth MSFT --classification-basis fcf-per-share
```

Control how optional forward EPS evidence is treated:

```bash
uv run ian fcf-growth MSFT --forward-policy display-only
uv run ian fcf-growth MSFT --forward-policy confirmation
uv run ian fcf-growth MSFT --forward-policy hard-gate
```

The current production SEC provider may not supply forward analyst-consensus evidence. A hard gate therefore returns `INDETERMINATE` when that required evidence is unavailable. See the [Free Cash Flow & Earnings Growth Strategy Guide](strategies/FCF_GROWTH.md).

## Presentation modes

The strategies use a common progressive-disclosure convention.

### Default — concise investor view

Omit presentation switches:

```bash
uv run ian graham-number KO
```

The default view emphasizes the result, its meaning, key source/freshness information, warnings, and limitations.

### `--details` — inspect the financial evidence

```bash
uv run ian graham-number KO --details
```

Use this for an investor-readable explanation of inputs, measurement bases, calculations and material assumptions. Graham reports show compact input evidence and formulas; Momentum explains its observation windows and signals; FCF shows an annual calculation table. Displayed values are rounded while calculations retain full precision. Inferred values remain identified as assumptions, not reported facts.

### `--diagnostics` — inspect software resolution behavior

```bash
uv run ian graham-number KO --diagnostics
```

Diagnostics retain complete technical provenance as well as resolution behavior: original provider fields, recursive component lineage, notes, retrieval/cache timing, identity metadata and share-context identifiers. Use this view or JSON to audit the evidence behind the shorter details report.

### `--json` — machine-readable output

```bash
uv run ian graham-number KO --json
```

Every strategy document has the same header and the same tail. Keys are written in this order, not sorted:

| Part | Keys, in order | Meaning |
| :--- | :--- | :--- |
| Header | `schema_version` | The document's own version |
| | `analysis`, `method` | Which strategy and method wrote it |
| | `ticker` | The instrument |
| | `status` | Whether the calculation ran, as a calculation status (`ok`, `not_applicable`, `invalid_input`, `input_unavailable` or `provider_error`). Never a verdict |
| | `provider_failure` | Why a `provider_error` status happened, when the adapter classified the failure: one of `provider_unreachable`, `provider_rate_limited`, `provider_unexpected_response` or `provider_no_data` as `reason_code`, and `inputs`, each failed input with its `provider_id` and `kind`. `null` for every other status, and for a provider failure the adapter could not classify. It is the element the failure document carries |
| | `provider_check` | What one test request found for each provider `provider_failure` names, as a list of `provider_id` and `verdict` entries; see [After a provider failure](#after-a-provider-failure-the-first-line). `null` on success, for a failure that names no provider, and for every document `runs show --json` writes |
| | `requested_as_of` | The point in time you asked for with `--as-of`; `null` means now |
| | `effective_as_of` | The instant the analysis was evaluated at: `requested_as_of` when given, else the execution time |
| | `security_identity`, `instrument_kind` | The identity and instrument-kind evidence the run retained |
| Body | The strategy's own keys | Listed in its schema |
| Tail | `warnings`, `limitations`, `diagnostics` | Lists of strings, strings and entries |

A verdict lives in the body: Momentum's trend is `result.trend` (`BULLISH`, `BEARISH` or `UNKNOWN`), and FCF Growth's screen is `classification`. Momentum's `status` is `ok` for every document it writes, because a calculation that cannot run fails instead. The latest data date Momentum used is `source.data_as_of`.

A Graham document's `quote` part carries `provider_failure` (`input` `current_price`, `provider_id`, `kind`) when the optional quote failed with a classified provider failure, otherwise `null`; it does not change `status`. A Graham document's body begins with `price_comparison` (`status`, `reason`, `percent`, `security_unit_evidence`, `provenance`, `quote_freshness`); its `percent` matches `result.margin_of_safety_percent`, and a comparison that was not made is `null`.

Presentation versions: Momentum **9**, Graham Number **10**, Graham Growth **10**, FCF Growth **9**. FCF's canonical result schema is **5** and its method version **2**.

Each strategy's document is described by a published schema: `schemas/momentum.schema.json`, `schemas/graham-number.schema.json`, `schemas/graham-growth.schema.json` and `schemas/fcf-growth.schema.json`. `runs show --json` writes the saved run's own strategy document, described by the same schema as the direct command's. Every key is always present: a value that is absent is `null`, not an omitted key. The document's `schema_version` is independent of the method version and of the stored result's schema version, which FCF Growth also writes (`method_version`, `result_schema_version`, directly after the header).

Quote timing distinguishes original retrieval from market observation. Filing venue evidence is separate from current identity. Momentum retains cache/provider resolution evidence and a typed crossover result. Missing numeric values remain `null`, never zero or non-standard `NaN`.

Post-parse execution failures also produce one JSON failure document with a null result, a stable `reason_code`, a `reason` sentence and sanitized diagnostics; the process exits with code 1. The same document is written by the workspace commands that offer `--json` (`watchlist show`, `watchlist rename`, `watchlist delete`, `runs list`, `runs show` and `refresh`), with `analysis`, `method` and `ticker` null. A `reason_code` value is never renamed or removed, so branch on it and not on `reason`; treat a value you do not recognise as a generic failure and read `status`. Exit code 2 means one thing: the command line itself was rejected before any command code ran (an unknown option or command, a missing argument or required option, a value of the wrong type or outside a declared choice), with usage text on standard error and no JSON. Every check a command makes on what you typed after that (the ticker, `--as-of`, `--data-provider`, the exclusive `--details`, `--diagnostics` and `--json`, a window or a policy, a watchlist name, a run ID, `--limit`, `--workers`, `--provider`, `--database-url`, `--report` and the rest) is an `invalid_parameter` failure: one sentence that names the offending options or arguments, exit 1, and with `--json` the failure document, whose `parameters` lists them (an option by its long spelling, an argument by its upper-case name such as `TICKER`). A command with no `--json` writes the sentence to standard error. The same mistake can therefore exit differently depending on who checks it: a missing `--expected-growth` on `graham-growth` is rejected by the parser (exit 2), and on `watchlist create --analysis graham-growth` by the command (exit 1). `parameters` is `null` for every other failure. The failure document's `schema_version` is 10; after a provider failure it carries `provider_check` beside `provider_failure`, as the strategy documents do. The schema is published as `schemas/failure.schema.json`. A successfully calculated FCF screen `FAIL` is not an execution failure.

The failure's code chooses its `reason` message, and the same code gives the same message on every command, including the `error` of a failed `refresh` job. A provider failure names the provider and the ticker (`Unable to analyze KO: sec_edgar is limiting requests.`). `historical_quality`, `no_eligible_observations`, every `database_*` code, `invalid_parameter` and `configuration_error` show the application's own text. `invalid_input` is `Unable to analyze <ticker>: invalid analysis inputs or provider data.`, and `execution_error` is `Unable to analyze <ticker>: the analysis failed unexpectedly.` A failure after the analysis finished, while its result was being saved (`--save-run`, or a `refresh` that saves), is `<ticker> was analyzed, but the result could not be saved.` under the code it classifies to (`invalid_stored_run`, `execution_error` or `invalid_input`). No message names the strategy; the command you typed, and the `analysis` and `method` fields of the failure document, say which one it was. The exception's own text goes to the log with its traceback.

Financial cache bypass is available through `--no-cache` on both Graham commands and `fcf-growth`. Quote responses expire independently after 300 seconds by default, even when annual-fact cache reuse is unlimited. Set the `IAN_QUOTE_CACHE_TTL_SECONDS` environment setting to a finite nonnegative value; zero disables quote reuse. An expired quote is refreshed once without substituting a stale value on failure. Old quotes with an unspecified cache basis are refreshed under the descriptive quote basis; annual caches and database schema are unchanged.

[Machine-readable output](GLOSSARY.md#machine-readable-output) is structured for another program to consume reliably rather than primarily for a person to read. Investment Analysis Engine currently uses [JSON](GLOSSARY.md#json-javascript-object-notation) for this mode.

JSON intentionally retains stable machine identifiers such as snake_case field names where those identifiers are part of the programmatic contract.

## Historical / point-in-time analysis

Where supported:

```bash
uv run ian graham-number KO --as-of 2025-12-31
uv run ian fcf-growth MSFT --as-of 2025-12-31
```

`--as-of` creates an information boundary. Financial facts that had not yet been published by that date cannot be used merely because their reporting period ended earlier. See [`as_of`](GLOSSARY.md#as_of), [publication date](GLOSSARY.md#available-at--filing-date--publication-date), and [look-ahead bias](GLOSSARY.md#look-ahead-bias).

A provider that only supplies today's quote does not manufacture a historical quote. A historical calculation may therefore succeed without a market-price comparison.

## Overrides

An [override](GLOSSARY.md#override) explicitly supplies a value instead of accepting the normal resolved value.

Examples:

```bash
uv run ian graham-number KO --eps 3.25 --bvps 8.10
uv run ian graham-number KO --current-price 75
```

Overrides are recorded as overrides rather than being presented as provider-verified evidence. See the strategy guide before overriding a value whose measurement basis matters.

## Selecting a data source

The Graham commands and `fcf-growth` take `--data-provider`; SEC EDGAR (`sec_edgar`) is the only accepted value and the default. Investment Analysis Engine rejects an unsupported value rather than silently substituting a different source or financial basis.

## When a command cannot produce a result

Common reasons include:

- the ticker is invalid or unsupported;
- a required financial fact is unavailable;
- the selected method does not apply to the supplied facts;
- a requested historical boundary excludes later-published information;
- a selected data source does not support that field/date; or
- a configured external service could not be reached.

Start with the ordinary error message. Use `--details` or `--diagnostics` when you need more evidence.

## After a provider failure: the first line

When `momentum`, `graham-number`, `graham-growth` or `fcf-growth` fails because a data provider failed, or `refresh`
has a job that failed that way, the application sends one small test request to that provider and prints what it
found as the first line, before the usual failure text, and in `--json` as the `provider_check` element of the
document. The provider is the one the failure names. The test request tests the provider, not your request, so a
line states only what the test request found. It offers no remedy.

| First line (Yahoo Finance shown) | What it means |
| :--- | :--- |
| `Yahoo Finance is not answering: a test request also failed.` | The test request did not get a response. |
| `Yahoo Finance is limiting requests: a test request was also refused.` | The provider refused the test request because it is limiting requests. |
| `Yahoo Finance answered a test request in a form this application does not read.` | The provider answered, but not in the shape the application reads. |
| `Yahoo Finance returned no data for a known test ticker. It may be limiting requests.` | The provider answered with nothing for a ticker that always has data. |
| `Yahoo Finance answered a test request normally. The failure may be specific to this request.` | The test request worked, so the failure may lie with your ticker, date or other inputs. |
| `Yahoo Finance was not checked (the provider check is turned off).` | You turned the check off, with `--no-provider-check` or the `IAN_PROVIDER_CHECK` setting. No request was made. |
| `Yahoo Finance could not be checked.` | The check could not run (for example SEC access is not set up), the provider has no check, or the check itself failed. No verdict was reached. |

The line goes to the same stream as the failure text it precedes: standard error in the concise and details views,
and where `--diagnostics` writes the report to standard output, there. For `refresh` the line precedes the summary
on standard output. A command that failed on two providers prints one line for each. A failure that names no
provider (`provider_error`) gets no line, and neither does a failed optional input, such as a current quote, on an
analysis that otherwise succeeded.

A command sends the test request at most once per provider per run, and `refresh` sends it once after the whole
batch, however many tickers failed. It does not retry the failed call, repair anything, or change the exit code or
the failure text; if the test request itself goes wrong, the failure is still reported as before.

With `--json` the test request is sent in the same way, nothing extra is printed to either stream, and the finding is
the document's `provider_check` element. It sits directly after `provider_failure` in the failure document and in
each strategy document, and is the last key of the `refresh` summary. Its value is:

- `null` when there is nothing to report: on success, for a failure that names no provider (`provider_error`),
  for a failed optional input on an analysis that otherwise succeeded, and in every document `runs show --json`
  writes, because replaying a saved run makes no live request and the verdict is never stored;
- otherwise a list with one entry per provider the failure names, in the order of their most severe failed kind
  (`unreachable`, `rate_limited`, `unexpected_response`, `no_data`), each with `provider_id` and `verdict`. The
  `refresh` summary lists each provider once, whichever jobs failed on it.

`verdict` is one of six values, matching the lines above in order: `unreachable`, `rate_limited`,
`unexpected_response`, `no_data`, `healthy` and `not_checked`. When the check is turned off the entries are still
present, with `not_checked`. Branch on `verdict`; the lines are sentences for people.

In `--json` mode a failed call can therefore take up to 12 seconds longer for each provider it names (the time limit
plus a short grace period, 24 seconds when a `refresh` implicates both providers), because the test request runs before
the document is written. Use `--no-provider-check`, or set `IAN_PROVIDER_CHECK=false`, to avoid the wait. The option
`--no-provider-check` is on exactly these five commands. Two engine settings, read as environment variables in the
same way as the others, control the check everywhere:

| Setting | Default | Meaning |
| :--- | :--- | :--- |
| `IAN_PROVIDER_CHECK` | `true` | Set to `false` to turn the check off for every command. |
| `IAN_PROVIDER_CHECK_TIMEOUT_SECONDS` | `10` | The time limit for the whole test request, above 0 and at most 60 seconds. |

## Checking that Yahoo and SEC EDGAR still answer

```bash
uv run ian health
uv run ian health --provider yfinance
uv run ian health --json
```

`ian health` makes a few small requests to each online data provider and prints one line per provider: the
verdict (`ok`, `unreachable`, `rate limited`, `unexpected response`, `no data`, `not configured` or `failed`), what it
requested and how long it took, and the reason when it did not pass. `not configured` means SEC EDGAR access is
not set up (see [Installation](INSTALLATION.md)); `failed` means an unexpected error inside the check. The exit
code is 0 when every check passed and 1 otherwise; an unknown `--provider` is an `invalid_parameter` failure (exit 1, the sentence on standard error, or with `--json` the failure document rather than the health document).

With `--json` the command writes one document to standard output and nothing else, whether or not every check
passed; it is not the failure document described above. The document is published as
`schemas/provider-health.schema.json`. Branch on each provider's `verdict`, which is `ok`, `unreachable`,
`rate_limited`, `unexpected_response`, `no_data`, `not_configured` or `failed`; `probe` and `detail` are sentences for people.
Each provider also has a `library` object, `{"name": "yfinance", "version": "..."}`, with the installed version of the
library the application reaches the provider through, or `null` where there is none (SEC EDGAR). The library is
pinned, so an unchanged version means a new failure came from the provider's side. The document's `schema_version`
is 3. The text output is unchanged.
`rate limited` means the provider is limiting requests (HTTP 429, or Yahoo's own rate-limit error), and it exits `1`
like every outcome but `ok`. Two cases are deliberately not `rate limited`. An empty Yahoo history is still `no data`:
the yfinance library hides its rate-limit error inside the history download and returns an empty frame, so a
throttled download cannot be told from an empty answer. An SEC HTTP 403 is still `unreachable`: SEC answers it for a
blocked client and for a rejected identity alike, so it cannot be told apart from a rejected identity. The
maintainer's runbook is [Provider Debugging](../project/PROVIDER_DEBUGGING.md).

## Optional local AI

The commands above are deterministic analysis commands and do not require a local LLM.

Local-AI orchestration/synthesis is an additional capability. The optional Golden Suite mode below can evaluate local-model selection behavior; it does not move financial arithmetic into the model. See [Hardware & Local AI](HARDWARE.md).

## Golden Suite evaluation

The Golden Suite is a technical benchmark rather than an investor analysis strategy. Its default mode uses only tracked deterministic fixtures and does not contact Ollama or live financial-data providers:

```bash
uv run ian evaluate --report artifacts/evaluations/deterministic.json
```

Use `--case GRN-01` to run one stable case. The report path is required; add `--overwrite` only when you intentionally want to replace an existing report.

Optional model-selection evaluation is explicitly opt-in and remains separate from deterministic financial verification:

```bash
uv run ian evaluate --mode ollama --model MODEL_TAG --ollama-endpoint http://127.0.0.1:11434 --report artifacts/evaluations/ollama.json
```

The command returns a non-zero status when a requested benchmark case fails or is skipped. For report fields, failure interpretation, empirical repetitions, and fixture maintenance, see [Evaluations & Golden Suite](../EVALUATIONS.md).
