# REASONS System Canvas: Step 1 - Local Orchestration Engine

* **System Lifecycle Phase:** Sprint Phase 1, Step 1
* **Target Model(s):** `qwen2.5-coder:14b-instruct-q4_K_M` (Light Mode Default); `qwen2.5-coder:32b` / `deepseek-r1:32b` (Optional Full Dual-Tier Mode)
* **Budget Ceiling:** $0.00 (strict local LLM execution; no cloud LLM API calls)
* **Status:** Current Step 1 architecture baseline
* **Related Master Plan:** `MASTER_PLAN.md`
* **Related Discovery Workbook:** `DISCOVERY_WORKBOOK.md`
* **Last Updated:** 2026-08-16

This document defines the architectural intent and Step 1 implementation blueprint. Implementation details may evolve provided the stated architectural invariants and acceptance criteria remain satisfied.  
Step 2.1 will further expand the telemetry portion.  

---

## 1. R - Requirements (System Context & Definition of Done)

### Background & Intent

The system requires a lightweight, robust, native Python engine to orchestrate financial data tools without pulling in bulky external orchestration frameworks. It must execute a predictable, bounded planning loop using localized, quantized open-source LLMs operating on a single-machine local setup, with Light Mode as the default.

### Acceptance Criteria (DoD)

* **AC-1 (Local LLM Boundary):** The orchestration engine performs no network communication with external services; LLM inference occurs exclusively through configured local/loopback model providers.
* **AC-2 (Schema Determinism):** Every registered Pydantic-backed tool produces a valid Ollama-compatible JSON schema through the canonical schema-generation path, with automated tests covering all supported tool-definition variants.
* **AC-3 (Resilient Self-Correction):** The orchestration loop detects execution failures or type errors and automatically injects an error context back to the model, allowing up to 3 repair attempts before cleanly aborting.

The local-network restriction applies to the orchestration/LLM boundary. External financial-data access, where required by higher-level application components, is performed by explicitly registered data tools rather than by the LLM or orchestration engine itself.

---

## 2. E - Entities (Domain Objects & Data Boundaries)

* **AgentContext:** Holds the orchestration state machine, active token-window monitoring state, and the conversation/application context required for a task. Diagnostic model output may be retained separately from user-visible conversation state.
* **ToolDefinition:** Internal representation of a registered tool, including its callable, name, description, argument schema, and metadata required for registration, schema generation, and dispatch.
* **ToolRegistry:** Centralized registrar of `ToolDefinition` objects. It maps registered Python callables and their Pydantic field specifications to JSON schemas and callable references.
* **ParsedToolCall:** Structured container produced by `ToolParser` containing a validated `tool_name` and dictionary of `arguments`.
* **ToolExecutionResult:** Envelope returned by `ToolDispatcher` containing execution status, timing metadata (`execution_time_ms`), payload outputs, and error information.

---

## 3. A - Approach (Strategic & Technical Architecture)

* **Framework-Free Loop:** Use plain asynchronous Python (`asyncio`) around an `httpx.AsyncClient` communicating directly with configured local Ollama endpoints.
* **Model-Output Normalization:** `ToolParser` normalizes model-specific auxiliary/reasoning delimiters and extracts the tool-call payload before downstream execution. For models that emit `<think>...</think>` blocks, these are treated as model-specific output that is not part of the tool-call payload.
* **Dynamic Tool Schema Generation:** Use Pydantic models plus Python introspection to derive Ollama-compatible tool schemas from registered callables. `inspect.signature()` supplies callable parameter information; docstrings supply human-readable descriptions where applicable.
* **Deterministic Execution Boundary:** The LLM selects registered tools and supplies structured arguments; deterministic Python code performs the actual tool execution and validation.

---

## 4. S - Structure (Module Boundaries & Layout)

The Step 1 implementation is organized around the following logical module boundaries. Filenames and internal organization may evolve provided these responsibilities and architectural boundaries remain intact.

```text
src/
├── config.py                 # Canonical ProjectSettings (pydantic-settings)
├── core/
│   ├── constants.py
│   └── telemetry/            # Structured trajectory telemetry (Step 2.1+)
├── llm/                      # Ollama client & schema boundary
├── tools/                    # Registry, schema generation, parser, dispatcher
├── orchestrator/             # Planner loop, context, rules, types
├── data/
│   ├── *client.py            # External provider adapters (BaseDataClient)
│   └── repositories/         # Typed DAOs (Step 3.2+)
├── analysis/                 # Pure deterministic analytics
├── reporting/                # Report generation (Step 7+)
└── utils/                    # Operational logger, workers
```

### Architectural Boundaries

The Step 1 orchestration boundary is:

```text
Local LLM
    │
    │ tool selection + structured arguments
    ▼
Tool Registry / Schema Layer
    │
    ▼
Tool Dispatcher
    │
    │ registered callable only
    ▼
Deterministic Python Tool
    │
    │ validated result
    ▼
Tool Execution Result
    │
    ▼
Orchestration Context / Local LLM
```

The following invariants apply:

* The LLM cannot execute arbitrary Python, shell commands, or operating-system commands.
* The LLM cannot directly access the filesystem or external network.
* Only explicitly registered tools can expose capabilities to the orchestration engine.
* Tools own any external capabilities they require, such as financial-data retrieval.
* Deterministic calculations and validation remain outside the LLM.
* The orchestrator owns execution policy, retry limits, and failure handling.

---

## 5. O - Operations (Method-Level Technical Blueprint)

### `schema_generator.py` → `ToolRegistry.to_ollama_tools()`

* **Input:** Registered `ToolDefinition` objects.
* **Behavior:** Transforms registered tool definitions into Ollama-compatible tool JSON structures (`type: "function"` with `name`, `description`, and `parameters`).

### `parser.py` → `ToolParser.parse(raw_output: str)`

* **Input:** Raw text returned by the local LLM.
* **Behavior:** Normalizes model-specific auxiliary output, extracts JSON objects from raw text or supported Markdown JSON blocks, validates parameters against the registered tool schema, and returns a `ParsedToolCall`.

### `dispatcher.py` → `ToolDispatcher.dispatch(parsed_call: ParsedToolCall)`

* **Input:** Validated `ParsedToolCall`.
* **Behavior:** Invokes only the registered Python callable associated with the requested tool, measures execution latency, captures exceptions without crashing the runner, and returns a `ToolExecutionResult`.

---

## 6. N - Norms (Engineering Standards & Quality Gates)

* **Strict Type Safety:** All supported source code must pass `mypy --strict` with zero errors. Dynamically typed external data must be validated at system boundaries before entering strongly typed application code.
* **Linting & Style:** CI verification must use non-mutating checks: `uv run ruff check .` and `uv run ruff format --check .`. Developers may use `ruff check --fix` and `ruff format` locally to repair formatting/lint issues.
* **Testing Coverage:** Every operational module requires corresponding unit tests under `tests/` (for example, `tests/tools/test_schema_generator.py`, `tests/tools/test_parser.py`, and `tests/tools/test_dispatcher.py`, as applicable to the implementation).
* **Project Entry Points:** All supported execution workflows run via `uv run` from the project root.

---

## 7. S - Safeguards (Local Boundary Guardrails)

* **Infinite Loop Circuit Breaker:** The system loop must hard-abort if iterations surpass `max_steps = 10` for a single task context, preventing runaway local computation.
* **Workspace Boundary Safety:** File-writing or system tools must validate and resolve paths against designated project-relative directories (`reports/`, `logs/`, `data/`) and must not permit traversal outside the authorized workspace.
* **Graceful Recovery Envelope:** If an underlying tool fails during dispatch, `ToolExecutionResult` wraps the failure information and passes it back to the orchestration context for agent self-correction.
* **No Arbitrary Shell/Code Execution:** The orchestration engine may invoke only explicitly registered tools. Model-generated text must never be interpreted as arbitrary Python, shell, or system commands.
* **Bounded Recovery:** `max_steps = 10` applies to the complete orchestration trajectory for a single task, while `max_repair_attempts = 3` applies to recovery from an individual tool/execution failure.
