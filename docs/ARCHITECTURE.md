# REASONS System Canvas: Step 1 — Local Orchestration Engine

* System Lifecycle Phase: Sprint Phase 1, Step 1
* Target Model(s): deepseek-r1:14b (Split RAM/VRAM Reasoner), qwen2.5-coder:7b / qwen2.5-coder:14b (Tool Executer)
* Budget Ceiling: $0.00 (Strict local execution, no cloud API calls)

---

## 1. R — Requirements (System Context & Definition of Done)

### Background & Intent
The system requires a lightweight, robust, native Python engine to orchestrate financial data tools without pulling in bulky external orchestration frameworks. It must execute a predictable, deterministic planning loop using localized, quantized open-source LLMs operating on a single-machine LAN setup.

### Acceptance Criteria (DoD)
* AC-1 (Zero Cloud Dependency): The engine initializes, routes messages, generates schemas, and executes code with absolutely zero networking requests outside the local subnet.
* AC-2 (Schema Determinism): 100% of Pydantic tools map dynamically to valid JSON schemas recognizable by local models (`to_ollama_tools()`).
* AC-3 (Resilient Self-Correction): The orchestration loop detects execution failures or type errors and automatically injects an error context back to the model, allowing up to 3 repair attempts before cleanly aborting.

---

## 2. E — Entities (Domain Objects & Data Boundaries)

* AgentContext: Holds the chat state machine, active token window monitors, and the raw conversation log (including think blocks if emitted by reasoning models).
* ToolRegistry: A centralized registrar mapping Python function signatures and Pydantic field specifications to JSON schemas and dynamic function callables.
* ParsedToolCall: Structured container produced by `ToolParser` containing validated `tool_name` and dictionary `arguments`.
* ToolExecutionResult: Envelope returned by `ToolDispatcher` containing status, timing metadata (`execution_time_ms`), payload outputs, and error strings.

---

## 3. A — Approach (Strategic & Technical Architecture)

* Framework-Free Loop: Use plain asynchronous Python (`asyncio`) wrapped around an `httpx.AsyncClient` pointing straight to local Ollama endpoints.
* Reasoning-Execution Bifurcation: Extract and strip `<think>...</think>` tags (e.g., DeepSeek-R1 outputs) in `ToolParser` before downstream execution to clean payload processing while logging diagnostics.
* Pure Schema Generation: Dynamic schema mapping powered by `pydantic.create_model()` and Python `inspect.signature` docstrings via `schema_generator.py`. Converts native Python callables directly into Ollama tool payloads.

---

## 4. S — Structure (File Topology & Layout)

The implementation strictly maintains the following file layout under `src/core/`:

```text
src/
└── core/
    ├── __init__.py
    └── tools/
        ├── __init__.py
        ├── schema_generator.py   # ToolRegistry & Ollama JSON schema generator
        ├── parser.py             # ToolParser & payload extractor (<think> tag stripper)
        └── dispatcher.py         # ToolDispatcher & timing result envelope
```

---

## 5. O — Operations (Method-Level Technical Blueprint)

### schema_generator.py -> ToolRegistry.to_ollama_tools()
* Input: Registered tool functions.
* Behavior: Transforms internal `ToolDefinition` objects into Ollama-compliant tool JSON structures (`type: "function"` with `name`, `description`, and `parameters`).

### parser.py -> ToolParser.parse(raw_output: str)
* Input: Raw text string returned by local LLM.
* Behavior: Strips `<think>` tags, extracts JSON objects from raw text or markdown ```json blocks, validates parameters against schema, and returns a `ParsedToolCall`.

### dispatcher.py -> ToolDispatcher.dispatch(parsed_call: ParsedToolCall)
* Input: Validated `ParsedToolCall`.
* Behavior: Dynamically invokes registered Python callables (`tool_def.callable_func(**args)`), measures execution latency, captures exceptions without crashing the runner, and returns a `ToolExecutionResult`.

---

## 6. N — Norms (Engineering Standards & Quality Gates)

* Strict Type-Safety: `uv run python -m mypy --config-file ./.mypyrc src` compliance across all modules. No raw untyped `Any` allocations allowed.
* Linting & Style: Code must clean-pass `uv run ruff check --fix . && uv run ruff format .` without warnings.
* Testing Coverage: Every operational module requires corresponding unit tests under `tests/core/` (e.g., `tests/core/test_tools.py`).
* Project Entry Points: All execution workflows run via `uv run` from project root.

---

## 7. S — Safeguards (Local Boundary Guardrails)

* Infinite Loop Circuit Breaker: The system loop must hard-abort if iterations surpass `max_turns = 5` for a single task context, preventing local hardware thrashing.
* Workspace Boundary Safety: File-writing or system tools must validate paths against the workspace root.
* Graceful Recovery Envelope: If an underlying tool fails during dispatch, `ToolExecutionResult` wraps the exception string and passes it back to the orchestration context for agent self-correction.