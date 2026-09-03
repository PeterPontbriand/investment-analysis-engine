# Step 2.6 Reliability Limits Slice Plan

**Status:** Complete and approved at Gate C on 2026-09-03<br/>
**Milestone owner:** [v0.2 Implementation Plan](../IMPLEMENTATION_PLAN.md)<br/>
**Architecture:** [Financial Data Agents Architecture](../../../ARCHITECTURE.md#9-failure-and-reliability-boundary)<br/>
**Master Plan:** [Financial Data Agents Master Plan](../../../MASTER_PLAN.md#6-failure-taxonomy--handling-strategy)

## 1. Purpose and authority

This document turns Step 2.6 into bounded implementation handoffs. It is
subordinate to the milestone implementation plan and owns the detailed
reliability contract where that plan is intentionally brief. It does not
authorize Step 3 persistence work, change financial calculations, or make
telemetry a business-control dependency.

Step 2.6 prevents orchestration from consuming unbounded time, planning steps,
or retry attempts. A limit breach is an expected terminal runtime outcome: it
must be observable, diagnosable, and returned without an unhandled exception.

## 2. Current-state findings

- `OrchestratorConfig.max_steps` already defaults to 10, but exhaustion returns
  only a terminal text message.
- `SchemaConfig.max_validation_retries` already defaults to 3 and bounds schema
  repair within one planning step.
- `LLMClient.generate()` currently passes `timeout=None`.
- `AsyncToolDispatcher` has no timeout boundary, and synchronous handlers run on
  the event-loop thread.
- unexpected orchestration exceptions are recorded at lower boundaries where
  applicable but are re-raised from the run.
- `RECOVERY_ATTEMPTED` exists in the telemetry vocabulary but is not emitted by
  the schema-repair loop.
- `TrajectoryRecorder` writes events but does not expose a bounded recent-event
  view for terminal diagnostics.

These are starting conditions, not permission for unrelated refactoring.

## 3. Fixed reliability contract

### 3.1 Configuration and defaults

Introduce one immutable typed `ReliabilityLimits` model, owned by the
orchestrator reliability boundary and loaded through `ProjectSettings`. An
`OrchestratorConfig` may receive an explicit instance for deterministic tests or
per-run overrides; otherwise it uses the settings-derived value. There must be
one effective value for each limit in a run.

| Limit | Default | Meaning |
| :--- | ---: | :--- |
| Maximum planning steps | 10 | Existing inclusive loop bound |
| Maximum transient retries | 3 | Total corrective retries for one operation |
| Maximum consecutive schema violations | 4 | Initial invalid response plus three corrective retries |
| Overall run timeout | 300 s | Monotonic deadline from run start through terminal result |
| Planning-step timeout | 180 s | LLM/schema repair plus all tools in one step |
| LLM-call timeout | 120 s | One provider request, including response-body receipt |
| Tool-call timeout | 60 s | One registered tool invocation |
| Recent diagnostic events | 5 | Sanitized in-memory trajectory summaries included on breach |

All numeric limits are strictly positive except retry counts, which may be zero.
Environment overrides use the existing nested-settings convention under
`reliability_limits`, rather than ad hoc environment reads in runtime modules.

The existing `max_steps` and schema retry inputs must be migrated without
silently changing their defaults or breaking supported construction paths. The
implementation must not leave two independently authoritative values. Any
compatibility adapter is bounded to input normalization and must reject
conflicting explicit values.

### 3.2 Deadline semantics and precedence

- All elapsed-time decisions use `time.monotonic()` or the event loop's
  monotonic clock. Wall-clock timestamps remain telemetry only.
- The overall deadline starts immediately before `RUN_START` is recorded.
- A step deadline starts immediately before `STEP_START` is recorded.
- Each LLM or tool operation receives the earliest of its own deadline, its
  step deadline, and the overall run deadline.
- The terminal reason identifies the deadline that actually expired:
  `overall_timeout`, `step_timeout`, `llm_timeout`, or `tool_timeout`.
- A deadline is checked before each planning step and before and after each
  LLM/tool boundary. Starting new work after its effective deadline is
  forbidden.
- Timeout handling must use bounded async primitives and must preserve
  `finally` cleanup, span closure, `RUN_END`, telemetry flush, and client-owned
  cleanup responsibilities.

An asynchronous operation is cancelled on timeout. A synchronous tool handler
must be moved off the event-loop thread before a timeout can be enforced, but
Python cannot safely kill arbitrary running thread work. Therefore:

- the caller stops awaiting a timed-out synchronous handler and returns a
  terminal timeout outcome;
- the diagnostic states that cancellation was not confirmed;
- tool handlers remain responsible for their own lower-level I/O timeouts and
  idempotency; and
- Step 2.6 does not add processes, forceful thread termination, or speculative
  rollback machinery.

### 3.3 Retry and error-threshold semantics

A retry is a repeated attempt at the same logical operation. The original
attempt is not a retry. Every retry emits `RECOVERY_ATTEMPTED` before the
repeated call with the sanitized failure category, retry number, configured
maximum, step index, and causal span linkage.

For Step 2.6:

- schema validation failures retain their existing corrective-prompt flow;
- the fourth consecutive invalid response trips
  `schema_violation_limit` under the defaults above;
- a valid schema response resets the consecutive-schema counter;
- the counter does not reset merely because parsing fallback produced a tool
  request;
- timeout breaches are terminal and are never themselves retried by the
  orchestrator;
- LLM transport failures may be retried only when explicitly classified as
  transient (connection interruption, HTTP 429, or HTTP 5xx);
- malformed/provider-invalid requests, authentication/authorization failures,
  and other HTTP 4xx failures are non-recoverable;
- tool failures are not automatically retried in Step 2.6 because the current
  dispatcher has no reviewed retry-safety/idempotency contract; and
- telemetry failures remain fail-open and neither consume retry budget nor trip
  the circuit.

Transient retry numbering and schema-violation counting are separate evidence,
but no operation may exceed the configured transient-retry maximum. Backoff may
be added only as a bounded, deterministic configuration with injectable waiting
for tests; it is not required for the initial step.

### 3.4 Circuit state and trip reasons

Use a small request-scoped `CircuitBreaker` or equivalently named reliability
controller. It owns monotonic deadlines and counters only. It must not select
strategies, interpret financial results, query persistence, or depend on a
working telemetry sink.

The closed trip-reason vocabulary is:

- `max_steps_exceeded`;
- `overall_timeout`;
- `step_timeout`;
- `llm_timeout`;
- `tool_timeout`;
- `transient_retry_limit`;
- `schema_violation_limit`.

The controller is created once per orchestration run. A trip is idempotent: the
first reason is authoritative, no new work begins afterward, and cleanup may not
replace it with a secondary failure.

### 3.5 Structured terminal outcome

Extend the existing terminal step/run contract minimally rather than creating a
parallel orchestration result hierarchy. A reliability failure contains:

- stable trip reason;
- safe human-readable message;
- `run_id`;
- final step number, when one started;
- configured threshold and observed value or elapsed duration;
- up to the configured number of recent sanitized trajectory-event summaries;
- whether cancellation was confirmed, when relevant; and
- no raw prompts, tool arguments/results, secrets, tracebacks, or private model
  reasoning.

The CLI renders this failure and exits nonzero. Library consumers receive the
typed terminal result. A reliability trip is not raised as an unhandled
exception. External cancellation (`CancelledError`), interpreter shutdown, and
programmer defects remain distinct from a circuit trip and must not be falsely
reported as one.

The human diagnostic begins with the trip reason and `run_id`, then reports the
limit and recent sanitized events. If telemetry is disabled or unavailable, an
empty recent-event collection is valid and the reliability outcome still works.

### 3.6 Telemetry contract

- Emit `RECOVERY_ATTEMPTED` for every actual retry, including schema repair.
- Record a classified `ERROR` when a limit trips.
- End the active operation and step spans exactly once where they were started.
- Emit one `RUN_END` whose payload carries the same terminal reason as the typed
  result.
- Retain only a bounded in-memory deque of already-sanitized event summaries for
  diagnostics; persistent sink readback is not required.
- Sink failure must not affect deadlines, counters, terminal reason, or cleanup.

No new telemetry event type is required unless implementation proves that the
existing `ERROR` plus `RUN_END` representation cannot express a trip without
ambiguity. Such a vocabulary change requires review before adoption.

## 4. Scope boundaries

### In scope

- the main `AgentOrchestrator` execution path;
- LLM calls made by that path, including schema repair calls;
- tools dispatched by that path;
- the CLI boundary that consumes orchestration terminal results;
- deterministic reliability unit/integration tests; and
- directly affected configuration, architecture, user, and milestone docs.

### Out of scope

- financial formula, strategy, provider-mapping, or applicability changes;
- SQLite or other Step 3 persistence;
- automatic retries for tools without a retry-safety contract;
- token-budget enforcement when providers omit token counts;
- process isolation or forceful termination of synchronous work;
- unattended scheduling, monitoring, or notifications;
- real provider calls or real local-model calls in automated tests; and
- broad redesign of `LLMClient`, the dispatcher, telemetry, or CLI.

The empirical Golden runner may continue to pass `max_steps`, but Step 2.6 does
not expand into a second reliability implementation inside evaluation code. It
must use the shared orchestrator boundary where applicable. Any evaluator-only
batch timeout is a separate evaluation concern and requires explicit scope.

## 5. Slice sequence and review gates

### Slice A — contracts and configuration

**Objective:** establish the typed policy and failure vocabulary without
changing runtime behavior.

**Owned work**

1. Add `ReliabilityLimits`, trip-reason, circuit-state, and typed failure models
   at the narrow orchestrator boundary.
2. Integrate settings and explicit per-run overrides with conflict validation.
3. Add a clock/deadline seam suitable for deterministic tests.
4. Add focused model/configuration tests for defaults, validation,
   serialization, override precedence, and conflicting legacy inputs.

**Gate A:** focused Ruff, formatting, strict mypy, and tests. Stop for human
review of public contracts and defaults before enforcement work.

**Gate A result:** Slice A is implemented and work is stopped for review. The
typed policy, terminal-failure and circuit-state contracts, monotonic clock
seam, settings integration, and bounded legacy-input normalization are in
place. The focused reliability/orchestrator/configuration suite passed 57 tests.
The final complete repository gate passed Ruff, formatting, strict mypy, and
1,315 tests at 88% reported coverage. Slice B had not started at Gate A.

**Gate A approval:** The human approved Slice A on 2026-09-02 and authorized
Slice B. The approved contracts and defaults are now fixed for enforcement.

### Slice B — enforcement and telemetry

**Objective:** enforce the approved policy throughout one orchestration run.

**Owned work**

1. Consult the circuit before each step and around each LLM/tool operation.
2. Enforce effective overall, step, LLM, and tool deadlines with cleanup-safe
   cancellation.
3. Apply schema and transient-failure counters and emit
   `RECOVERY_ATTEMPTED` before every retry.
4. Provide bounded sanitized recent-event summaries independently of sink
   success.
5. Add deterministic tests using fake clients/tools and controlled clocks for
   normal completion, every trip reason, deadline precedence, counter reset,
   retry exhaustion, telemetry failure, and cancellation cleanup.

If Slice B proves too large for coherent review, split it without changing
contracts:

- **B1:** deadlines, timeout enforcement, and cancellation cleanup;
- **B2:** retries, schema threshold, recent-event diagnostics, and telemetry.

**Gate B:** focused gates plus the complete repository quality wrapper. Stop for
human review of enforcement and failure evidence before CLI closeout.

**Gate B result:** Slice B was implemented as the planned B1/B2 contract without
an intermediate scope change. The request-scoped circuit now enforces earliest
overall/step/LLM/tool deadlines, cooperative async cancellation, explicit
unconfirmed cancellation for thread-backed synchronous tools, exact retry and
schema-violation caps, and no-work-after-trip behavior. Classified LLM transport
retries and schema repair emit `RECOVERY_ATTEMPTED`; telemetry retains only the
configured number of sanitized event summaries and remains fail-open. Logical
request/tool/step spans close through `finally` paths. The focused
reliability/orchestrator/telemetry suite passed 78 tests. The complete repository
gate passed Ruff, formatting, strict mypy, and 1,329 tests at 88% reported
coverage.

**Gate B approval:** The human approved Slice B on 2026-09-03 and authorized
Slice C. The enforcement and telemetry behavior above is fixed for closeout.

### Slice C — terminal presentation and closeout

**Objective:** expose reliability outcomes coherently and synchronize the
documentation.

**Owned work**

1. Return the typed reliability failure through the existing terminal result
   path and render its concise CLI diagnostic with nonzero exit status.
2. Add integration tests proving no reliability breach escapes as an unhandled
   exception and each diagnostic contains the correct `run_id` and reason.
3. Document supported settings/defaults and the synchronous-handler cancellation
   limitation.
4. Run the complete quality wrapper and reconcile every Step 2.6 acceptance
   criterion.

**Gate C:** stop for final human review. Do not mark Step 2.6 complete, commit,
push, open/merge a PR, or begin Step 3.1 without the corresponding explicit
human authorization.

**Gate C result:** Slice C exposes `ReliabilityFailure` on the terminal
`AgentStepResult`, and the empirical evaluation consumer uses that typed field
without inspecting model prose. Failed command-line evaluations render concise
case diagnostics containing the stable reason and `run_id`, write their report,
and exit nonzero. Deterministic integration coverage proves reliability trips
remain terminal results, and a settings test proves the documented nested
environment override. The focused Slice C/reliability/evaluation checks passed
85 tests. The complete repository wrapper passed Ruff, formatting, strict mypy
over 191 source files, and 1,331 tests at 88% reported coverage. No real API,
provider, or LLM endpoint was called. Work is stopped at Gate C pending final
human review.

**Gate C remediation decision:** The optional LAN smoke run on 2026-09-03
reached Ollama 0.33.2 but received HTTP 404 because `LLMClient` posted a
non-native payload to `/generate`. Gate C is reopened before final approval.
Correct the client to use Ollama's native non-streaming `/api/chat` contract for
message lists and `/api/generate` contract for plain prompts, update mocked wire
tests so they no longer encode the invalid endpoint/payload, rerun the complete
quality gate, and then ask the operator to repeat the optional smoke run. The
observed report and exit status behaved correctly; the missing strategy/method
results were downstream consequences of the transport failure.

**Gate C remediation result:** `LLMClient` now sends message-list requests to
native non-streaming `/api/chat` with `model`, `messages`, `options`, and
`stream: false`; plain-string requests use `/api/generate` with `model`,
`prompt`, `options`, and `stream: false`. Response extraction follows the
matching native response shape, and the obsolete console `print()` error path
was removed. Mock-transport tests now assert the exact native paths and payloads
for both request forms. The focused transport/reliability/evaluation suite
passed 37 tests. The complete repository wrapper passed Ruff, formatting,
strict mypy over 191 source files, and 1,332 tests at 88% reported coverage. The
operator was then asked to repeat Appendix A before final Gate C review.

**Final Gate C approval:** The human approved the complete Step 2.6
implementation, native Ollama remediation, deterministic verification, and
optional LAN smoke evidence on 2026-09-03. Step 2.6 is complete. This approval
permits the implementation checkpoint and PR workflow but does not itself begin
Step 3.1 implementation.

## 6. Verification matrix

Automated verification is deterministic and uses no real network, provider, or
LLM endpoint.

| Scenario | Required evidence |
| :--- | :--- |
| Normal completion | No trip; existing result and ordered telemetry preserved |
| Maximum steps | Typed `max_steps_exceeded`; no step 11 under defaults |
| Overall timeout | Overall reason wins and no later work begins |
| Step timeout | Active step ends cleanly; run ends with matching reason |
| LLM timeout | Request cancellation attempted; typed diagnostic returned |
| Async tool timeout | Tool cancellation attempted; no subsequent tool starts |
| Sync tool timeout | Event loop remains responsive; cancellation-not-confirmed is explicit |
| Transient LLM recovery | At most three retries; one recovery event per retry |
| Non-recoverable LLM error | No retry; existing error boundary remains intact |
| Schema recovery | Valid response resets consecutive counter |
| Schema exhaustion | Fourth consecutive violation trips under defaults |
| Telemetry sink failure | Same result/reason as with a healthy sink |
| Cleanup | Spans, `RUN_END`, flush, and close each occur as specified |
| Configuration | Defaults and environment/per-run overrides need no code edits |

Tests should inject clocks/events rather than sleep against real time. Tiny
event-loop yields may coordinate cancellation tests, but pass/fail behavior must
not depend on machine speed.

## 7. Local-model decision

Real local-model execution is not required for Step 2.6 implementation or
acceptance. Reliability logic is better proven with deterministic delayed,
failing, malformed, and cancellation-aware fakes. Model speed varies with
hardware and load and cannot establish correct deadline or retry semantics.

An optional manual smoke run may be recorded after Slice C, but it cannot replace
the deterministic tests or block Step 2.6 closeout. Empirical native-schema
compatibility for the supported Light Mode model remains owned by the existing
Step 2.2 follow-up and Step 3.5 exit criterion.

## 8. Step acceptance criteria

- [x] The fixed defaults are implemented and documented through one effective
  typed configuration path.
- [x] Maximum steps, all four timeout scopes, transient retries, and consecutive
  schema violations are bounded as specified.
- [x] Every breach returns a typed terminal failure with a clear `run_id`-linked
  diagnostic and never escapes as an unhandled reliability exception.
- [x] Every actual retry emits sanitized `RECOVERY_ATTEMPTED` telemetry.
- [x] Recent-event diagnostics remain bounded and telemetry failures remain
  fail-open.
- [x] Deterministic tests cover the full verification matrix without live API or
  LLM calls.
- [x] Focused checks and the complete repository quality gate pass.
- [x] Architecture, milestone, configuration, and user-facing documentation are
  synchronized to implemented behavior.
- [x] The final diff receives explicit human approval before Step 3.1 begins.

## 9. Immediate next action

Create the approved Step 2.6 implementation checkpoint and proceed through the
PR workflow. Plan Step 3.1 separately; this closeout does not itself begin its
implementation.

## Appendix A — Optional post-Slice-C local-model smoke run

### A.1 Purpose and status

This optional operator check exercises the implemented orchestration,
evaluation, terminal-diagnostic, report-writing, and process-status boundaries
against a real Ollama endpoint on the workstation or a trusted LAN inference
server. It is empirical evidence only. It is not a Step 2.6 acceptance
criterion, does not replace the deterministic tests, and
must not block closeout because model output and response time vary by model,
hardware, server version, and current load.

The nominal run checks that a bounded real-model request can traverse the
production path. The timeout probe temporarily lowers the LLM-call limit to
make the Step 2.6 terminal diagnostic observable. Neither run contacts a live
financial-data provider: the empirical Golden runner supplies tracked fixtures
to production tool dispatch.

### A.2 Prerequisites

1. Run from the repository root in PowerShell with the project environment
   already synchronized.
2. Ensure Ollama is running on either the workstation or a trusted LAN
   inference server and that the intended model is already installed on that
   server. The workstation does not need the Ollama executable when it is only
   acting as the evaluation client. Do not pull or install a model merely to
   satisfy Step 2.6.
3. Use `financial-data-agents-step-2-5:latest`, the project-recommended
   installed evaluation model, unless the operator is intentionally comparing
   another installed model. Choose the HTTP endpoint reachable from the
   workstation. Use `http://127.0.0.1:11434` only for workstation-local Ollama.
   For a LAN server, use its trusted hostname or LAN address, for example
   `http://inference-server:11434` or `http://192.168.1.19:11434`. The server
   must listen on the LAN interface and its host firewall must permit the
   workstation to reach the selected port. Do not expose an unauthenticated
   Ollama endpoint to the public internet for this smoke run.
4. Keep generated JSON reports and raw trajectory logs local. Do not commit
   them; they are operational artifacts rather than reviewed fixtures.

Confirm the CLI and Ollama endpoint before running the smoke cases:

```powershell
$smokeModel = "financial-data-agents-step-2-5:latest"
# Use http://127.0.0.1:11434 only for workstation-local Ollama.
$smokeEndpoint = "http://192.168.1.19:11434"
uv run financial-agents evaluate --help
$ollamaVersion = Invoke-RestMethod "$smokeEndpoint/api/version"
$availableModels = (Invoke-RestMethod "$smokeEndpoint/api/tags").models.name
$ollamaVersion
$availableModels
$availableModels -contains $smokeModel
```

Expected prerequisite result: the CLI displays its evaluation options, the
version endpoint returns an Ollama version, the tags endpoint returns the models
installed on that same server, and the final expression prints `True`. A local
`ollama list` command is an optional equivalent check only when the Ollama CLI
is installed on the workstation and targets the same server; it is neither
required nor authoritative for a LAN-only setup. Stop and classify the check as
**not run — environment unavailable** if the REST endpoints are unreachable or
the selected model is absent; that is not a Step 2.6 defect.

### A.3 Nominal bounded run

Run one stable case once, with deterministic sampling and an explicit
three-step cap:

```powershell
$nominalReport = "artifacts/evaluations/step-2.6-smoke-nominal.json"
uv run financial-agents evaluate `
    --mode ollama `
    --case GRN-01 `
    --model $smokeModel `
    --ollama-endpoint $smokeEndpoint `
    --temperature 0 `
    --repetitions 1 `
    --max-steps 3 `
    --report $nominalReport `
    --overwrite
$nominalExit = $LASTEXITCODE
$nominalExit
```

Expected result:

- the process terminates without hanging and writes `$nominalReport`;
- exit `0` means the case passed its empirical selection criteria;
- exit `1` with a written report may instead mean the model chose an incorrect
  tool/argument, ended before executing the expected tool, or reached a
  reliability cap. Inspect `failure_reasons` before classifying it;
- a model-selection failure alone is empirical model evidence, not a Step 2.6
  defect; and
- an unhandled traceback, missing report after completed evaluation, or work
  continuing beyond the configured cap is a Step 2.6 investigation trigger.

Inspect the concise result and retained configuration:

```powershell
Select-String -Path $nominalReport -SimpleMatch `
    -Pattern 'execution_mode', 'model_id', 'max_steps', 'failure_reasons', 'trajectory_id'
```

### A.4 Deliberate LLM-timeout probe

The following command launches a new process with a 1-millisecond LLM-call
limit. This is intended to expire before a real local generation completes. The
override applies only while the environment variable exists in the current
PowerShell session.

```powershell
$timeoutReport = "artifacts/evaluations/step-2.6-smoke-llm-timeout.json"
$env:reliability_limits__llm_call_timeout_seconds = "0.001"
try {
    uv run financial-agents evaluate `
        --mode ollama `
        --case GRN-01 `
        --model $smokeModel `
        --ollama-endpoint $smokeEndpoint `
        --temperature 0 `
        --repetitions 1 `
        --max-steps 3 `
        --report $timeoutReport `
        --overwrite
    $timeoutExit = $LASTEXITCODE
} finally {
    Remove-Item Env:\reliability_limits__llm_call_timeout_seconds `
        -ErrorAction SilentlyContinue
}
```

Expected result:

- the command returns promptly with exit `1` and still writes `$timeoutReport`;
- the console diagnostic and report `failure_reasons` contain `llm_timeout` and
  a UUID-form `run_id`;
- the failure is reported as an evaluation failure rather than an unhandled
  Python exception; and
- later planning or tool work does not begin after the timeout.

Verify the retained diagnostic:

```powershell
Select-String -Path $timeoutReport -SimpleMatch `
    -Pattern 'llm_timeout', 'run_id=', 'failure_reasons', 'trajectory_id'
```

If an unusually fast or mocked endpoint completes within one millisecond, the
probe is **inconclusive**, not failed. Record that fact; do not progressively
increase timing sensitivity or treat wall-clock behavior as deterministic
proof. The automated fake-clock and cancellation tests remain authoritative.

### A.5 Evidence record

Record the following in the review discussion or an explicitly approved
sanitized closeout note. Do not paste raw trajectory logs or secrets:

| Field | Value to record |
| :--- | :--- |
| Date/time and operator environment | Local timestamp, OS, and relevant hardware summary |
| Ollama version | Value returned by `/api/version` |
| Model | Exact installed model tag |
| Commands | Nominal and timeout-probe commands, noting any intentional changes |
| Nominal result | Exit code, report path, case outcome, and classified failure if any |
| Timeout result | Exit code, `llm_timeout` observed or inconclusive, and sanitized `run_id` |
| Artifacts | Local report paths; confirmation that raw/generated artifacts were not committed |

Possible conclusions are **passed as optional smoke evidence**, **inconclusive
because timing/model behavior did not exercise the intended branch**, or **not
run because the optional environment was unavailable**. Only a reproducible
contract violation—such as an escaped reliability exception, absent typed
diagnostic, incorrect exit status, missing completed report, or post-trip
work—should be raised as a Step 2.6 defect.

### A.6 Recorded smoke evidence — 2026-09-03

The operator ran both smoke commands from Windows against trusted LAN endpoint
`http://192.168.1.19:11434`, Ollama 0.33.2, using
`financial-data-agents-step-2-5:latest`. Hardware details were not recorded.
Generated reports remain local and untracked under `artifacts/evaluations/`.

The first nominal attempt exposed the invalid pre-existing `/generate` wire
contract and returned HTTP 404. That finding reopened Gate C and led to the
native `/api/chat` and `/api/generate` remediation recorded above. After the
remediation, the operator repeated the nominal run:

- report: `artifacts/evaluations/step-2.6-smoke-nominal.json`;
- exit: `1`, with a completed report rather than an escaped exception;
- fixture, strategy-selection, and Graham-method-selection components passed;
- the model issued the correct `analyze_graham_number` call three times rather
  than terminating;
- the configured three-step cap returned typed `max_steps_exceeded`; and
- diagnostic `run_id` and `trajectory_id` both equal
  `f30d79f9-dbaf-47ea-85cb-01c395a3c235`.

The repeated correct tool call is empirical model loop behavior, not a Step 2.6
defect. The circuit terminated it at the configured boundary.

The deliberate 1-millisecond LLM-timeout probe then produced:

- report: `artifacts/evaluations/step-2.6-smoke-llm-timeout.json`;
- exit: `1`, with a completed report rather than an escaped exception;
- typed `llm_timeout` in the console and report; and
- diagnostic `run_id` and `trajectory_id` both equal
  `30b15577-b0ef-4698-9919-5e6cddaf8e93`.

The missing strategy and method outcomes in the timeout report are expected
downstream consequences of timing out before the first model response. Together
the reruns are classified as **passed optional smoke evidence** for the native
LAN transport, bounded max-step termination, typed timeout termination,
diagnostic identity, report preservation, and nonzero process status. They do
not replace deterministic acceptance evidence or establish general model
quality.
