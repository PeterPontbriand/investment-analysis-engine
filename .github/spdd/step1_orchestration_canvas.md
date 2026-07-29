# REASONS System Canvas: Step 1 — Local Orchestration Engine

* System Lifecycle Phase: Sprint Phase 1, Step 1
* Target Model(s): deepseek-r1:14b (Split RAM/VRAM Reasoner), qwen2.5-coder:7b (Tool Executer)
* Budget Ceiling: $0.00 (Strict local execution, no cloud API calls)

---

## 1. R — Requirements (System Context & Definition of Done)

### Background & Intent
The system requires a lightweight, robust, native Python engine to orchestrate financial data tools without pulling in bulky external orchestration frameworks. It must execute a predictable, deterministic planning loop using localized, quantized open-source LLMs operating on a single-machine LAN setup.

### Acceptance Criteria (DoD)
* AC-1 (Zero Cloud Dependency): The engine initializes, routes messages, generates schemas, and executes code with absolutely zero networking requests outside the local subnet.
* AC-2 (Schema Determinism): 100% of Pydantic tools map dynamically to valid JSON schemas recognizable by local models.
* AC-3 (Resilient Self-Correction): The orchestration loop detects execution failures or type errors and automatically injects an error context back to the model, allowing up to 3 repair attempts before cleanly aborting.

---

## 2. E — Entities (Domain Objects & Data Boundaries)

* AgentContext: Holds the chat state machine, active token window monitors, and the raw conversation log (including think blocks if emitted by reasoning models).
* ToolRegistry: A centralized registrar mapping simple Python function string names to their executable underlying functions and their respective auto-generated structural JSON schemas.
* ToolCallRequest / ToolCallResponse: Strict Pydantic objects defining the inputs parsed from the model and the results returned to the loop.

---

## 3. A — Approach (Strategic & Technical Architecture)

* Framework-Free Loop: Use plain asynchronous Python (asyncio) wrapped around an httpx.AsyncClient pointing straight to the local Ollama /v1/chat/completions API endpoint.
* Reasoning-Execution Bifurcation: The prompt structures instruct the system runner to explicitly isolate reasoning streams. If deepseek-r1 is running, its <think> output tags are logged to a localized diagnostic file but stripped out before formatting downstream context messages to save token density.
* Pure Schema Generation: Avoid hardcoded tool prompt strings. Leverage pydantic.TypeAdapter(Model).json_schema() to guarantee that what the developer builds in code matches what the agent reads as documentation.

---

## 4. S — Structure (File Topology & Layout)

The implementation will strictly create and maintain the following files under src/:

src/
└── core/
    ├── __init__.py
    ├── config.py          # Port bindings, model configurations, path variables
    ├── exceptions.py      # Custom exceptions: ToolValidationError, LoopExhaustedError
    ├── llm_client.py      # Bare-metal Async HTTP client wrapping local endpoints
    ├── registry.py        # Decorators for wrapping Python functions into tools
    └── orchestrator.py    # The core continuous state-machine evaluation loop

---

## 5. O — Operations (Method-Level Technical Blueprint)

### llm_client.py -> OllamaClient.generate_structured(...)
* Input: messages: List[Dict], response_model: Type[BaseModel]
* Behavior: Execute a POST request to local port. Must explicitly populate the options={"temperature": 0.0} to suppress hallucinations. If the model fails to return a clean JSON parsing structure matching response_model, raise a localized JSONDecodeError.

### registry.py -> ToolRegistry.register(func)
* Input: A callable Python function featuring complete type hints and docstrings.
* Behavior: Use inspect and Pydantic to parse args into a schema model dynamically. Store the callable into an internal dictionary map keyed by the exact function name string.

### orchestrator.py -> ExecutionLoop.run(initial_prompt: str)
* Behavior: 
    1. Loop until current_turn > max_turns or a final terminal answer is generated.
    2. Format the system context by combining system instructions with active ToolRegistry schemas.
    3. Dispatch context to OllamaClient.
    4. Parse tool payload calls out of the response string.
    5. Safely execute the target tool function within a try/except boundary.
    6. Append output strings or formatted exceptions directly back to memory history logs.

---

## 6. N — Norms (Engineering Standards & Quality Gates)

* Strict Type-Safety: mypy --strict compliance across all modules. No raw untyped Any allocations allowed.
* Linting & Style: Code must clean-pass ruff check . and ruff format . execution gates without warnings.
* Testing Coverage: Every operational module requires a corresponding test case under tests/core/ leveraging pytest and pytest-asyncio. 
* Sync Rule: If any function footprint changes during development, this Canvas file must be updated first, followed by a Git commit, before execution code updates are run.

---

## 7. S — Safeguards (Local Boundary Guardrails)

* Infinite Loop Circuit Breaker: The system loop must hard-abort if iterations surpass max_turns = 5 for a single task context, preventing local hardware thrashing.
* Memory Boundary Safety: File-writing tools or command-execution tools developed downstream must restrict their execution paths to the workspace root directory via absolute validation mapping checks. No arbitrary system tool executions are permitted.
* Graceful Recovery Payload: If an exception is raised by an underlying function tool, do not crash the app runner. Capture the stack trace string, clean it, format it as a markdown instruction box, and return it to the LLM agent to prompt self-remediation.
