# Financial Data Agents – Development LLM Guardrails

These rules apply to agents that write, refactor, test, or maintain the codebase.
They are intentionally denser than the runtime rules.

## 1. Absolute Forbidden Actions
* NEVER commit secrets, API keys, `.env` files, `.sqlite`/`.db` files, or raw log files.
* NEVER install dependencies or edit `pyproject.toml` / `uv.lock` without explicit user permission.
* NEVER leave `print()` statements, bare `except:` blocks, or unhandled NaN/Inf values in production paths.
* NEVER hardcode financial parameters (risk-free rates, lookbacks, tickers); read from arguments or `src/config.py`.
* NEVER make real external network/API or LLM calls during unit tests; mock all external responses.
* NEVER write partial files, placeholder comments (`# TODO`, `# ... existing code ...`), or truncated snippets—always emit complete, runnable code.
* NEVER delete, comment out, or omit existing public methods, exported interfaces, helper utilities, or feature logic unless explicitly instructed; update tests first.
* NEVER ask the user to paste file contents; always use the `read_file` tool.

## 2. File Modification & Preservation
* Prefer full-file writes for any file under ~200 lines. Local models generate complete files more reliably than surgical patches.
* When editing larger files, keep SEARCH blocks short (5–10 lines), character-for-character exact (including whitespace), and free of placeholders.
* Feature Preservation: Before any refactor, run the existing test suite to establish a baseline. Refactored code MUST pass the identical assertions.
* Clean Diffs: Do not alter unrelated formatting, indentation, imports, or comments outside the target scope.
* Always emit the complete function or class body that contains the change.

## 3. Python, Ruff & Syntactic Rules
* Target Python 3.12+ (project baseline). Code must pass `ruff check --fix` and `mypy --strict` (or the project’s configured equivalent).
* 100 % explicit type annotations on all function signatures, parameters, and return types (`-> None` when appropriate).
* Google-style docstrings required on every module, class, and public function. The first line MUST end with `.`, `!`, or `?`.
* Double quotes for strings, 4-space indentation, imports only at the absolute top of the file (never inside functions, classes, or control flow). Group: stdlib → third-party → local.
* Unused loop variables must be prefixed with `_` (Ruff B007).
* Prefer vectorized pandas/numpy operations; avoid row-wise Python loops over DataFrames.

## 4. Exact Logging Protocol
* Use the project’s centralized async logging system exclusively:
  - Call `setup_global_logging()` once at process start.
  - Obtain a logger via `setup_logger(__name__)`.
  - Prefer the context-manager form when injecting transient metadata:
    ```python
    with setup_logger(__name__) as adapter:
        adapter.set_extra({"ticker": "AAPL", "request_id": "..."})
        adapter.info("message")
    ```
* NEVER introduce a second logging system (`structlog`, plain `logging.getLogger` outside the utility, etc.).
* NEVER use `print()` for application flow.
* Levels: DEBUG for shapes/intermediates, INFO for milestones/timing, WARNING for fallbacks, ERROR with `exc_info=True`.

## 5. TDD, Verification Gate & Coverage
* Write or update tests in `tests/` (mirroring `src/` structure) BEFORE implementation code.
* Mandatory gate: run the relevant pytest suite (normally via `uv run pytest ...`) before declaring any task complete. Do not report success if tests fail.
* Mock every external API and local LLM endpoint.
* Minimum 85 % branch coverage on new financial-calculation modules; higher for `src/core/tools/` and `src/analysis/`.

## 6. Financial Invariants (Development Awareness)
* Always prefer Adjusted Close for returns, volatility, momentum, and performance calculations.
* Enforce short-window < long-window at runtime validation points.
* Explicitly handle empty series, NaN, Inf, and zero-volatility cases.
* Detailed formulas and edge-case expectations live in `docs/FINANCE_MATH.md` (load on demand).

## 7. OS, Shell & Execution
* Primary development environment: Windows 11 + PowerShell.
* Prefer PowerShell-compatible syntax. Use `pathlib.Path` or `os.path.join` for paths.
* Execute all project tools through `uv run ...` from the repository root.
* Quality-gate order: `uv run ruff check --fix .` → `uv run ruff format .` → type check → tests.

## 8. Human-in-the-Loop & Cost Gates
* Require explicit user confirmation before: file deletions, git resets/force-pushes, database migrations, opening PRs, or any structural repository change.
* Prompt before launching long-running compute loops or heavy backtests.

## 9. On-Demand Context Index
* Financial mathematics & formulas → `docs/FINANCE_MATH.md`
* Domain glossary & schemas → `docs/GLOSSARY.md`
* Architecture & orchestration canvas → `docs/ARCHITECTURE.md`
* Slash-command workflows → `.claude/commands/`
