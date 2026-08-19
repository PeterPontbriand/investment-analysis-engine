# /run-tests

**Purpose:** Run the relevant project tests and quality checks.

## Instructions

Use project tooling through `uv run`.

Typical full test/coverage command:

```bash
uv run pytest --cov=src --cov-report=term-missing
```

Focused example:

```bash
uv run pytest -k momentum
```

Rules:
- Mock/inject all external market-data and LLM interactions in deterministic tests.
- Do not assume tests must use yfinance-specific fixtures; prefer the active typed data contract.
- Project coverage target is ≥85% line coverage overall; new financial-analysis code must directly cover meaningful edge cases.
- If tests fail, diagnose the failure within the requested task scope rather than broadening into unrelated refactors.
- Follow the active milestone's exact completion quality gates.
