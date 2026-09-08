# R1 Contract and Implementation Handoff

**Status:** Gates R1-A and R1-B approved on 2026-09-06; documentation checkpoint b7625fd preceded R1-B checkpoint 36b8dbf. Gate R1-C approved on 2026-09-06; R1 complete and approved.
**Authority:** [Implementation Plan, R1](../IMPLEMENTATION_PLAN.md).
**Approval effect:** Approval of this record and the amended implementation plan
closed Gate R1-A and authorized R1-B. Subsequent Gate R1-B approval authorized
R1-C. Gate R1-C approval on 2026-09-06 closes R1; no later work is authorized.

## 1. Scope and ordering

R1-B adds method-specific configuration/analyzer wrappers over existing Graham
execution services. R1-C replaces the combined command and extracts applicable
CLI support. Preserve legacy public analyzer/config interfaces, orchestration
handlers/tool identities, service functions, resolver rules, numerical behavior,
provenance, applicability, and result schemas. R1 precedes Step 3.4 by scheduling
choice, not a technical prerequisite. No other strategy must adopt BaseAnalyzer.

## 2. Configuration contract

Add `GrahamNumberConfig` and `GrahamGrowthConfig` in
`src/analysis/graham_value/analyzer_config.py`, both with `extra="forbid"` and
`frozen=True`. No discriminator or presentation-mode field is needed: the model
type identifies the method; rendering is a caller responsibility.

| Field | Type/default | Applicability |
| :--- | :--- | :--- |
| `security_provider_id` | `str`, default `sec_edgar` | Both; trim/lowercase, reject blank |
| `quote_provider_id` | `str \| None`, default None | Both; derive from effective security provider if omitted; normalize explicit nonblank value |
| `eps_basis` | `Literal["three_year_average", "ttm"] \| None`, default None | Both; normalize text and resolve using the matrix below |
| `eps_override` | `float \| None`, default None | Both |
| `quote_override` | `float \| None`, default None | Both |
| `as_of` | `datetime \| None`, default None | Both; require timezone awareness when present |
| `use_cache` | `bool`, default True | Both |
| `bvps_override` | `float \| None`, default None | Number only |
| `expected_growth` | required `float` | Growth only |
| `aaa_yield_override` | required `float` | Growth only |

Normalized configs contain a resolved EPS basis and quote provider. Derive quote
provider as `yfinance` for `sec_edgar`, `massive` for `massive`, and the supplied
security provider for another injected provider. Other nonblank provider IDs
remain usable with explicit injected resolvers; production CLI composition still
rejects unsupported providers before fetching, using its existing failure path.

| Method/provider | Omitted EPS basis | Accepted explicit basis | Additional condition |
| :--- | :--- | :--- | :--- |
| Number / SEC | three_year_average | three_year_average | None |
| Number / Massive | three_year_average, then reject | ttm | Explicit BVPS override required; do not silently change the old default |
| Number / injected other | three_year_average | either supported basis | None |
| Growth / SEC | three_year_average | three_year_average | Growth and AAA yield required |
| Growth / Massive | ttm | ttm | Growth and AAA yield required |
| Growth / injected other | ttm | either supported basis | Growth and AAA yield required |

Reject blank/unknown EPS bases and cross-method fields, even when an extra
field is supplied as None. Trim/lowercase supported basis strings. Keep numeric
financial-validity decisions at existing service/resolver/calculator boundaries:
wrong types or missing required fields are config errors; numeric values that
previously produced typed invalid/unavailable results must not become new CLI
usage errors. Explicitly regression-test zero, negative, and non-finite inputs
against current service behavior; no invalid value may become a successful result.

## 3. Analyzer and resource contracts

Add `GrahamNumberAnalyzer` and `GrahamGrowthAnalyzer` in
`src/analysis/graham_value/analyzers.py`; expose them and their configs through
the package's existing `__init__.py` without removing existing exports.

- Each subclasses `BaseAnalyzer` with its concrete config and sets
  `config_schema` to that config class.
- Number constructor: injected `GrahamInputResolver`, keyword-only
  `default_ticker: str | None = None`, `instrument_profile: InstrumentProfile | None = None`.
- Growth constructor: the same dependencies plus required keyword-only
  `policy: GrahamGrowthCalculationPolicy`.
- `run_analysis(config, ticker=None)` returns `GrahamNumberAnalysis` or
  `GrahamGrowthAnalysis`, respectively, by delegating to the matching service.
- Use the explicit ticker when it is not None, otherwise the constructor default;
  trim/uppercase and reject missing/blank input. Do not invent a fallback symbol.
- The supplied profile is execution context, not part of the config. Service
  validation enforces its ticker match. The CLI builds one analyzer for the
  selected ticker/profile per invocation. An analyzer with a fixed profile is
  not a reusable cross-ticker profile lookup service.
- Pass normalized config fields, profile, and injected policy directly to the
  existing services. Return complete evidence including assembly, result, margin,
  requested boundary, and retained profile without reconstruction or relabeling.
- Composition owns provider/cache construction, closure, profile resolution, and
  reading configured growth constants. Analyzers borrow these objects, perform
  no implicit production setup, and do not close resources or create clocks.
  Existing resolver clocks and service temporal checks remain authoritative.
- Preserve `GrahamValueAnalyzer`/`GrahamValueConfig` and all current callers.
  Orchestration continues using service functions directly; no tool migration.

## 4. CLI contract and migration

The replacement command names are `graham-number` and `graham-growth`.
Remove `graham` and `--method`/`-m`; no compatibility alias or subcommand group.
Keep positional ticker and `--ticker`/`-t` alias with existing conflict behavior.

Both commands retain `--as-of`, `--data-provider`, `--no-cache`, `--eps`/`-e`,
`--eps-basis`, `--current-price`/`-p`, and the mutually exclusive presentation
options `--details`, `--diagnostics`, `--json`. Map these to the corresponding
config fields; `--no-cache` maps to `use_cache=False`. Quote-provider selection
remains internal; do not add a new CLI flag for it.

Number alone exposes `--bvps`. Growth alone requires `--expected-growth` with
aliases `--expected-growth-rate`/`-g`, and `--aaa-yield` with aliases
`--current-aaa-yield`/`-y`. Preserve existing option explanations, replacing
references to the removed `--method` selector with the appropriate command.
Command summaries: "Execute the Graham Number earnings-and-book-value screen."
and "Execute Graham Growth Value with explicit growth and AAA-yield assumptions."

| Old invocation | Replacement |
| :--- | :--- |
| `financial-agents graham KO` | `financial-agents graham-number KO` |
| `financial-agents graham KO --method number --bvps 20` | `financial-agents graham-number KO --bvps 20` |
| `financial-agents graham KO --method growth --expected-growth 5 --aaa-yield 4.5` | `financial-agents graham-growth KO --expected-growth 5 --aaa-yield 4.5` |

Other supported flags carry over unchanged to their applicable command.
Publish this mapping in the active usage guide during R1-C, update current
examples/help together, and preserve historical milestone evidence. Removed
commands/options must fail as usage errors; do not silently route them elsewhere.

## 5. CLI support and error handling

Use `src/cli_support.py`, retaining `src/cli.py:app` and its current entry point.
Move ticker, presentation-mode, as-of, and provider-normalization helpers and
both production resource context managers. Support code must not import cli.py;
move required imports/constants with the helpers to avoid circular imports.
Make ticker-usage diagnostics accept the invoking command name rather than
hard-coding the removed command. CLI parsing performs string/date conversion;
config validators perform method/provider combination checks.

Use a shared context manager for equivalent execution-error mechanics with
explicit command-specific message callbacks. Keep usage validation outside it;
translate Pydantic validation failures into concise option-specific
`typer.BadParameter` errors (exit 2), without raw model dumps. Propagate intentional
`typer.Exit` and usage exceptions before broad exception handling. Preserve
execution-error exit 1, successful/not-applicable statuses, stdout/stderr,
optional-quote handling, and each presentation mode. Do not treat every typed
unavailable result as an exception. Preserve cache closure on all exit paths.
Only applicable commands use each helper; do not add options to other commands
or merge financial and historical cache policy.

## 6. Files and verification

R1-B write allowlist:
- `src/analysis/graham_value/analyzer_config.py` (new)
- `src/analysis/graham_value/analyzers.py` (new)
- `src/analysis/graham_value/__init__.py` (exports only)
- `tests/analysis/graham_value/test_analyzer_config.py` (new)
- `tests/analysis/graham_value/test_method_analyzers.py` (new)
- R1 planning records for evidence/status only.

R1-C write scope: `src/cli.py`, new `src/cli_support.py`, affected CLI/composition
and help/schema tests under `tests/`, active user/command documentation, and R1
planning evidence. Before editing, enumerate the exact affected tests/docs from
imports, patch targets, command invocations, and entry-point references; record
that list in this file. No production changes outside the two CLI modules are
authorized by R1-C; escalate a demonstrated contract conflict for review.

Before each implementation slice, establish the full managed baseline. Test the
complete config matrix, service-equivalent typed results, explicit/default
ticker behavior, profile mismatch, legacy interfaces, and injected cache/provider
ownership. CLI regressions cover both new commands, removed invocations, all
aliases/defaults, usage errors, presentation modes, provider errors, optional
quotes, financial-cache reuse/bypass, historical-cache reuse, and exception
cleanup. Update moved-helper patch targets without weakening assertions. Use
only deterministic fixtures/mocks; do not call live providers or LLM endpoints.

Run the managed full quality gate after each implementation slice (Ruff,
formatting, strict mypy, pytest/coverage). Review the actual diff and evidence at
Gate R1-B before authorizing R1-C, and at Gate R1-C before completing R1. No
subsequent work begins automatically. No dependency change or database migration
is included in this authorization.

## 7. Approval record

On 2026-09-06, the project owner approved this handoff and authorized R1-B.
The subsequent instruction requires a checkpoint commit of all pending planning
documentation changes before any R1-B implementation edits. At that time R1-C
remained unauthorized pending Gate R1-B; the subsequent approval is recorded below.

Pre-implementation checkpoint verification passed on 2026-09-06: Ruff,
formatting, strict mypy, and the full deterministic pytest/coverage suite.
Artifacts: .tmp/quality-runs/20260906133144108-40088-8eda8918aa094309954f6509d9b88164/.
No production or test files were changed before this checkpoint.

## 8. R1-B implementation evidence

The documentation-only checkpoint was committed as `b7625fd` on
`docs/next-phase-planning` before any production/test changes. The complete
pre-implementation baseline passed 1,615 tests with 89% reported coverage.

Added the two frozen method configs, the two typed BaseAnalyzer wrappers,
package exports, and focused deterministic tests within the R1-B allowlist.
Services, resolver, legacy analyzer/config, CLI, orchestration, dependencies,
and persistence remain unchanged. Analyzers borrow the injected resolver,
policy, and profile; composition retains resource and clock ownership.

Verification covers the complete provider/EPS/default matrix, normalization,
required/cross-method/invalid-type fields, timezone awareness, frozen config
round trips, complete service evidence including resolution traces, explicit
and default tickers, profile mismatch and ETF applicability, retained policy
and profile, cache reuse/bypass, and ownership after execution exceptions.
Zero, negative, and non-finite values are compared with the unchanged services.
Growth's existing finite zero/negative EPS and growth semantics are retained;
fully override-driven security analysis remains unavailable. Invalid required
inputs do not become successful results; invalid optional quotes yield no margin.

The complete managed gate passed Ruff, formatting, strict mypy, and pytest
with 1,750 passing tests (135 new) and 89% reported coverage on 2026-09-06. The actual changed-file scope and patch whitespace
were reviewed. Final artifacts:
`.tmp/quality-runs/20260906133939615-1760-6e282d99d4eb4b6dab6ba06dc6567dc0/`.

**Review status:** Ready for Gate R1-B stakeholder review. No R1-C work,
implementation commit, push, or PR was performed. R1 completion and later work
remain separately gated.


## 9. R1-C authorization and affected-file inventory

The project owner approved Gate R1-B and authorized R1-C on 2026-09-06.
A checkpoint commit containing the approved R1-B changes has been created and pushed.

Production edits: src/cli.py and new src/cli_support.py only.
Affected existing tests identified from imports, patch targets, and invocations:
- tests/test_cli.py
- tests/test_cli_financial_cache.py
- tests/test_cli_historical_cache.py
- tests/test_cli_graham_nonpositive_growth.py
- tests/test_cli_graham_slice_f_routing.py
- tests/test_graham_growth_default_policy.py
- tests/data/test_massive_cli_configuration.py

New focused migration/support coverage: tests/test_cli_support.py and
tests/test_cli_graham_commands.py. Existing tests/test_cli_fcf_earnings_growth.py
and tests/evaluation/test_cli.py retain their imports and command entry point;
run them to verify preserved behavior.

Active documentation edits: README.md, docs/user/USAGE.md,
docs/user/QUICKSTART.md, docs/user/INSTALLATION.md, docs/user/SMOKE_TESTING.md,
docs/user/strategies/GRAHAM.md, and docs/user/GLOSSARY.md.
No command or entry-point changes were found in .claude/ or .github/.
Historical milestone command evidence remains unchanged.

## 10. R1-C implementation evidence

On 2026-09-06 the project owner authorized Codex to replace the unfinished
Cline implementation and approved a targeted rollback. Before rollback, the
affected CLI and scratch files were copied to
`.tmp/r1-c-recovery-20260906194623/`. The approved CLI baseline was restored
from `36b8dbf`; R1-B analyzer/config code and unrelated R2 planning were preserved.
No dependencies, database schema, services, or orchestration code changed.

The restored full managed baseline passed 1,750 tests at 89% reported coverage:
`.tmp/quality-runs/20260906194623719-44816-09021b39ea3741689294087b03c2bd44/`.

The two replacement commands construct the approved typed configs before
resource creation and call their corresponding analyzer. Removed the combined
command, method selector, `GrahamCliMethod`, and duplicated config validation.
Extracted ticker/presentation/date/provider parsing and both cache context
managers to `src/cli_support.py`. Shared exception mechanics retain explicit
command messages, intentional usage exits, typed statuses, and stream selection.
Updated the enumerated active guides and published the invocation migration table.

The existing test inventory was migrated without dropping test functions.
New regressions cover removed invocations, applicable help/options, short aliases,
normalized configs, both analyzers in every presentation mode, validation before
resource construction, exception cleanup, non-finite inputs, and ticker diagnostics.
Financial-cache reuse and bypass now exercise both Graham commands as well as FCF
Growth. Non-finite explicit quotes retain the existing `invalid_input` result;
unavailable provider quotes retain their existing optional-quote behavior.

Planning evidence also updates `../IMPLEMENTATION_PLAN.md` to reflect Gate R1-B
approval and the pending Gate R1-C review. This is status synchronization only.

Final managed gate passed on 2026-09-06: Ruff, formatting, strict mypy, and
1,809 deterministic tests (59 more than the restored baseline), with 89%
reported coverage. Artifacts:
`.tmp/quality-runs/20260906195900845-46700-7d90a4b6397e4f00abc9c6a5ea5f5b15/`.
The final diff and active command references were reviewed; `git diff --check`
passed. No live provider/model calls, commit, push, or PR were performed.
Ready for Gate R1-C stakeholder review; R1 is not marked complete and no later
implementation has been started by this work.

## 11. Final approval and R1 completion

On 2026-09-06, the project owner reviewed and explicitly approved the R1-C
implementation. This closes Gate R1-C and completes R1, including all three
review gates and the acceptance criteria in the implementation plan. The final
verification evidence in section 10 remains authoritative: 1,809 passing tests,
89% reported coverage, Ruff, formatting, and strict mypy.

The approval supersedes the historical pending-review status above. This update
records completion only; no commit, push, PR, or subsequent implementation is
authorized or performed by this record.

## Merged implementation checkpoint — 2026-09-07

[PR #29](https://github.com/PeterPontbriand/financial-data-agents/pull/29) merged
R1 and R2 into `main` on 2026-09-07 at 17:55:41 UTC. Merge commit:
`ca914b73281aaf5e618684098bb4f115c90972c5`; reviewed PR head:
`c4316425c52488c6574c93027235b9ac980e0803`. Their tracked trees are identical.
This closes the implementation/PR workflow; prior no-PR and pending-review
statements remain historical execution snapshots, superseded by final approval
and this merge record. No predecessor checkpoint or review gate remains open.

The [Step 3.2 handoff](../step-3.2/STEP_3_2_CONTRACT_AND_SLICE_PLAN.md) now owns
current planning. Its preparation is authorized by the subsequent project-owner
request; the R1/R2 merge itself does not authorize later implementation.
