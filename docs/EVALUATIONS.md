# Evaluations & Golden Suite

**Status:** Milestone v0.2 Step 2.5 is complete and approved as of 2026-08-31<br/>
**Governing sequence and acceptance criteria:** [Milestone v0.2 Implementation Plan](project/milestones/v0.2/IMPLEMENTATION_PLAN.md#4518-implementation-sequence)<br/>
**Formal implementation slices:** [Step 2.5 Golden Suite Slice Plan](project/milestones/v0.2/step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md)<br/>
**Current gate decision:** [Step 2.5 Gate M Review](project/milestones/v0.2/step-2.5/STEP_2_5_GATE_M_REVIEW.md)<br/>
**Closeout evidence:** [Step 2.5 Closeout Verification Record](project/milestones/v0.2/step-2.5/STEP_2_5_CLOSEOUT_RECORD.md)<br/>
**Architecture:** [Financial Data Agents Architecture](project/ARCHITECTURE.md#7-golden-suite-architecture-step-25)

## 1. Purpose

The Golden Suite is the project's reproducible benchmark for the approved v0.2 analytical strategies:

- Momentum;
- the Graham Number;
- the Graham growth-value method; and
- Free Cash Flow & Earnings Growth.

It evaluates deterministic financial behavior separately from local-model strategy and tool selection. It is an evaluation system, not a production data store, production cache, trajectory-log archive, or investor-facing Analysis Run library.

Step 2.5 implementation lives under `src/evaluation/`. The package consumes the existing strategy, market-data, financial-fact, provenance, resolution, tool-dispatch, and telemetry boundaries. It must not create a parallel strategy framework or force heterogeneous strategy results into one production result model.

## 2. Current implementation status

The tracked `src/evaluation/` package now contains typed Golden cases and expectation models, independently reviewed expected-value evidence, numerical and method/tool evaluators, aggregate result/report models, deterministic fixture composition, an evaluator self-test, and a deterministic runner. Existing deterministic market-data, Graham financial-fact, and annual FCF financial-fact providers live in `src/evaluation/fixtures/` without becoming production cache data.

Production strategy handlers are registered outside the evaluation and test packages through `src/orchestrator/analysis_tools.py`. The explicit tool names are `analyze_momentum`, `analyze_graham_number`, `analyze_graham_growth_value`, and `analyze_fcf_earnings_growth`. Their Pydantic argument models are available through the read-only `ANALYSIS_TOOL_ARGUMENT_MODELS` mapping. `register_analysis_tools(...)` attaches dependency-injected handlers to the existing `AsyncToolDispatcher`; the same seam accepts production adapters or deterministic fixture-backed analyzers and resolvers. Each handler preserves its strategy's native typed result rather than introducing a generic strategy-result model.

The current versioned deterministic suite contains nineteen stable case IDs across Momentum, both Graham methods, Graham resolution, FCF/Earnings Growth, and the reviewed SEC FPI/IFRS boundaries. The approved fifteen-case `h1-v2` suite remains historical benchmark evidence; Step 2.5A Slice D deliberately advanced the suite and fixture set to `h1-v3` by adding four cases without rewriting earlier case IDs or fixtures.

P1 hardening is complete and approved. Its evidence, mappings, implementation decisions, and review record are in the [P1 Instrument Applicability Mapping Record](project/milestones/v0.2/step-2.5/STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md). A known ETF remains applicable to Momentum but is `not_applicable` to both Graham methods and the existing company-level FCF Growth strategy. Unknown kind remains fail-open; it is never guessed from missing facts, a ticker, or a name.

P1 does not add persistence or another strategy. P2 — durable instrument profiles and a distinct ETF aggregate FCF-growth strategy — is planned only after Step 3.1. P2 may later extend the reviewed suite through the normal human-directed case-expansion process; it must not change existing case definitions, silently substitute for company-level FCF Growth, or turn production cache data into Golden fixtures.

Slice I added the optional empirical runner. It uses the production orchestration and tool-dispatch path with deterministic Golden fixtures, preserves every repetition independently, records observable model/runtime configuration, and suppresses raw model-response and prompt-message bodies from trajectory persistence. Normal tests mock the model client and never contact Ollama.

Slice J exposes both runners through `financial-agents evaluate`, adds explicit report-file handling and process-status semantics, and completes this operator guide. Slice K ran the full repository gate, recorded the final deterministic result and explicit absence of an optional empirical run separately, and reconciled every acceptance criterion in the [Closeout Verification Record](project/milestones/v0.2/step-2.5/STEP_2_5_CLOSEOUT_RECORD.md). The human approved the closeout on 2026-08-31. Step 2.5A D0 is the next implementation-planning handoff.

## 3. Execution modes

The suite has two explicitly separate modes.

### Deterministic/no-LLM mode

This mode validates fixture loading, shared data contracts, strategy calculations, expected numerical values, evaluator behavior, aggregation, and report serialization without calling an LLM or a live market-data provider.

Deterministic/no-LLM execution cannot measure LLM strategy or tool selection. Its strategy-selection component must be reported as `not_measured`; scripted execution or direct invocation must never be presented as a passing LLM-selection result.

### Real-local-Ollama mode

This optional empirical mode measures observable strategy, method, tool, and argument selection through the production orchestration and tool-dispatch boundaries as far as practical. It records the model identifier, Ollama configuration, relevant sampling settings, repetition policy, and nondeterministic outcomes.

Real-local-Ollama execution remains separate from deterministic regression tests and is not mandatory CI unless explicitly configured. Deterministic tests mock all local-model endpoints.

Each empirical repetition produces its own complete report. The runner does not vote, average, or replace divergent outcomes with a synthetic consensus. Numerical correctness is deliberately `not_measured` in this mode: deterministic/no-LLM execution remains the authority for fixture-backed financial results, while the empirical mode measures model-controlled selection and execution behavior.

## 4. Evaluation components

Reports distinguish at least:

- strategy/tool-selection correctness;
- Graham method-selection correctness where applicable;
- deterministic numerical correctness;
- fixture/data failures;
- other execution failures; and
- overall case pass/fail.

Expected native domain outcomes are benchmark results, not exceptions to the
benchmark. A case designed to prove `input_unavailable` or `not_applicable`
passes only when the exact expected status and material reason/availability
contract is observed. The same observed status is a classified failure when the
case expected success. Correct non-success domain outcomes must not be converted
automatically into fixture or execution failures.

Component denominators include only cases for which the component is actually measurable and applicable. In particular, `not_measured` strategy selection in deterministic/no-LLM mode is not silently converted to pass or fail and is not counted as an observed selection attempt.

The aggregate pass rate remains the number of executed cases satisfying all required case-level criteria divided by the total number of executed benchmark cases. Mode-specific required criteria and component metrics must remain explicit in the report. The milestone's ≥90% target is a measurement target and must not be used to weaken expectations, remove useful failing cases, or tune the benchmark instrument until a model passes.

## 5. Golden cases and fixtures

Every Golden Case is typed and identifies its case ID, description, task or prompt, fixture IDs, expected strategy/tool behavior, expected deterministic outputs, tolerances, required/permitted/forbidden behavior, pass rules, and optional tags.

Golden fixtures are tracked, deterministic, reviewable benchmark evidence. They must:

- use the shared market-data and financial-fact contracts;
- include only evidence required by their cases;
- retain relevant provider, source, retrieval, period, currency, timezone/date, transformation, schema-version, and reference metadata;
- fail explicitly when requested evidence is absent;
- never fall back to a live provider or mutable production cache;
- remain independent of SQLite and later production persistence; and
- preserve explicit `as_of` boundaries wherever dates affect eligibility.

Instrument-profile fixtures retain the normalized kind, raw provider classification, provider identity, and resolution timestamp required to audit applicability. A deterministic known-ETF case must obtain ETF status from that fixture evidence; absence of company facts alone is not ETF evidence.

Benchmark fixture implementations belong to the importable `src/evaluation/fixtures/` boundary rather than under `tests/`. Test modules may construct additional small fakes, but the runtime evaluation package must not import test code. The extracted deterministic providers preserve the approved provider-neutral contracts and remain separate from production cache data.

Expected numerical values are benchmark contract data. They must be verified using transparent reference calculations, a separate reference implementation, or sufficiently simple manual calculations. Production functions under test must never generate their own expected values. Tolerances are case-appropriate absolute and/or relative tolerances rather than one universal constant.

## 6. Benchmark composition

The original corrected fifteen-case set includes Momentum success and boundary behavior; the default and TTM Graham Number variants; Graham Number `not_applicable`, growth-value, missing-price, and input-resolution behavior; FCF/Earnings Growth success, nonmeaningful growth, period alignment, and historical `as_of` behavior; and the three additional ETF routes below.

The Gate M review established that one Graham-only ETF case did not prove the
cross-strategy applicability contract. Slice H added three cases against the same
reviewed ETF profile boundary: Momentum remains applicable, while Graham growth
value and company-level FCF Growth return their native `not_applicable` outcomes.
Together with the existing Graham Number case, the scenario covers all four
routes without treating the ticker as invalid or substituting an aggregate ETF
strategy.

At least one case must materially discriminate the requested strategy from a plausible wrong strategy. A discriminating case may also satisfy another required minimum category when that overlap is explicit and useful.

The current `h1-v3` suite contains nineteen cases. Its four Step 2.5A additions
cover a US-GAAP `20-F` success, an exact IFRS duration-fact success, an exact
IFRS CapEx-concept negative, and a security-unit negative. Strategy selection
remains `not_measured` in deterministic mode. Further expansion remains
review-driven, not automatic; each addition must version the suite/fixture set
and document the failure mode or signal it contributes.

## 7. Telemetry and reporting

End-to-end evaluation uses Step 2.1 trajectory telemetry as observable execution evidence where available. Telemetry may provide selected tool names, validated arguments, structured results, errors, recovery events, step boundaries, and run identity. It is observational evidence and must never control financial execution or substitute for benchmark expectations. Private reasoning and model-specific `<think>` content are not evaluation inputs.

The deterministic machine-readable report contains:

- `suite_id`, `suite_version`, and `fixture_set_version` identities;
- `execution_mode` and timezone-aware `executed_at`;
- the mode-specific `required_component_kinds`;
- case totals, executed/passed/failed/skipped counts, and `overall_pass_rate`;
- one metric for every component, including measured/applicable denominators;
- ordered per-case results, component evidence, and classified failure reasons; and
- a run or trajectory identity where available.

An empirical report adds a top-level session identity, model/provider configuration, the explicit nondeterministic-outcome policy, the requested repetition count, and `repetition_reports`. Every repetition report retains its own case results and trajectory identities. Deterministic and empirical files have related but intentionally different top-level schemas; consumers must inspect `execution_mode` or the empirical `repetition_reports` structure rather than combining their scores.

Generated reports and raw trajectories are local execution artifacts unless a separately reviewed sanitized result record is intentionally added. Secrets, API keys, raw operational logs, and raw trajectory logs must never be committed.

## 8. Evaluator self-test

The evaluator includes a regression test proving that an intentionally incorrect observed result is detected. The synthetic incorrect result is test input, not a normal benchmark case, and remains outside the benchmark denominator so a correctly detected failure does not make CI fail.

## 9. CLI and CI contract

Run the complete deterministic suite through the normal project workflow:

```bash
uv run financial-agents evaluate --report artifacts/evaluations/deterministic.json
```

Run one named case by stable ID:

```bash
uv run financial-agents evaluate --case GRN-01 --report artifacts/evaluations/grn-01.json
```

Case matching is case-insensitive, but reports always retain the canonical ID. The full reviewed catalog is used when `--case` is omitted. The report destination is mandatory. Parent directories are created as needed, and an existing report is protected unless replacement is explicit:

```bash
uv run financial-agents evaluate --report artifacts/evaluations/deterministic.json --overwrite
```

The optional empirical mode is activated only by `--mode ollama`:

```bash
uv run financial-agents evaluate --mode ollama --model MODEL_TAG --ollama-endpoint http://127.0.0.1:11434 --repetitions 3 --report artifacts/evaluations/ollama.json
```

`--model` and `--ollama-endpoint` fall back to the application configuration when omitted. `--temperature`, `--repetitions`, and `--max-steps` make the applied empirical configuration explicit. These options are rejected in deterministic mode so they cannot silently change benchmark semantics. Use `uv run financial-agents evaluate --help` for the complete option list.

Process status has operator and CI meaning:

- `0` — every requested case execution passed its mode-specific required criteria;
- `1` — at least one requested case failed or was skipped, the runner failed, or the report could not be written; and
- `2` — invalid CLI usage, such as an unknown case, empirical controls in deterministic mode, or an existing report without `--overwrite`.

The JSON report is still written when evaluation completes with benchmark failures, allowing CI and reviewers to inspect the evidence behind status `1`. Deterministic/no-LLM execution is the headless CI boundary. Real-model and network-dependent evaluation is never a mandatory CI dependency unless a separate CI configuration explicitly opts into it.

### Interpreting failures

Read the case's `failure_reasons` together with its component results:

- `strategy_selection` or `graham_method_selection` failures indicate an empirical model selected the wrong tool, method, or normalized arguments;
- `numerical_correctness` failures indicate deterministic observed values fell outside the case's reviewed tolerances;
- `fixture_status` failures indicate required benchmark evidence could not be composed or supplied; and
- `execution_status` failures indicate a production tool, orchestration step, or expected native domain outcome did not complete as required.

`not_applicable` and `not_measured` are explicit component outcomes, not hidden passes. A case can pass with them only when the mode and case contract make that outcome legitimate. Do not compare a deterministic report's numerical score directly with an empirical report's selection score or merge repeated empirical outcomes into one unofficial result.

## 10. Maintenance rules

- Add or change a case only with a documented reason and independently verified expectations.
- Preserve stable case IDs once results have been recorded.
- Version material case-schema, fixture-set, evaluator, and report-contract changes deliberately.
- Do not silently refresh fixture evidence or replace historical values with current provider data.
- Do not remove a useful failing case merely to improve a reported score.
- Keep deterministic and empirical local-model results clearly separated.
- Run the complete repository quality gate before Step 2.5 completion review.

When a case or fixture genuinely needs maintenance:

1. document the concrete failure mode or new signal the case contributes;
2. preserve an existing case ID, or assign a new stable ID rather than repurposing an old one;
3. update only tracked fixtures under `src/evaluation/fixtures/`, retaining provenance and point-in-time boundaries;
4. establish changed expected values independently of the production calculator under test;
5. version material case, fixture-set, evaluator, or report-contract changes deliberately;
6. add focused deterministic tests, then run and review the full deterministic report; and
7. keep generated reports and raw trajectories local unless a separate review explicitly approves a sanitized measured-result record.

Never refresh a fixture merely because current provider data differs, copy production cache contents into the benchmark, or remove a useful failure to improve the aggregate score.
