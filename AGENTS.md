# Financial Data Agents – Development LLM Guardrails

These rules apply to agents that write, refactor, test, document, or maintain this codebase.

## 1. Documentation precedence

When instructions differ, use this precedence:

1. explicit human request for the current task;
2. current active milestone implementation plan;
3. `docs/MASTER_PLAN.md`;
4. `docs/ARCHITECTURE.md` and `docs/DISCOVERY_WORKBOOK.md`;
5. specialized references such as `docs/FINANCE_MATH.md`;
6. README/convenience command files.

Do not blend contradictory instructions. Surface the conflict and follow the more specific/current source.

For Milestone v0.2, `docs/MILESTONE_v0_2_IMPLEMENTATION_PLAN.md` owns implementation sequencing, review gates, scope, and acceptance criteria.

## 2. Absolute forbidden actions

- NEVER commit secrets, API keys, `.env` files, SQLite/database files, or raw operational/trajectory logs.
- NEVER install dependencies or edit `pyproject.toml` / `uv.lock` without explicit user permission.
- NEVER introduce `print()` statements, bare `except:`, or silently propagate NaN/Inf values in production paths.
- NEVER bury financial assumptions as unexplained magic constants in calculation bodies. Intentional defaults belong in typed configuration/models and must be documented.
- NEVER make real external API or LLM calls during deterministic unit tests.
- NEVER leave partial files, placeholder comments, or truncated snippets.
- NEVER delete or remove existing public interfaces or behavior unless the task explicitly requires it.
- NEVER create a generic strategy/plugin/registry/factory hierarchy merely because two analyzers differ. Prefer existing `BaseAnalyzer`, tool dispatch, and dependency-injection patterns unless the active plan proves they are insufficient.
- NEVER turn telemetry into control flow or benchmark fixtures into production cache data.

## 3. Scope preservation

- Before refactoring, establish the relevant test baseline.
- Preserve unrelated behavior and formatting.
- A pre-existing rule violation in a legacy file is not permission to refactor unrelated code while touching that file.
- New or materially modified lines should follow current guardrails; opportunistic cleanup belongs in a separate task unless required to complete the requested change.
- Honor explicit review gates in the active milestone plan. If a step says to stop for human review, stop there.

## 4. Python, Ruff & typing

- Target Python 3.12+.
- All supported source must pass `mypy --strict`.
- Use explicit type annotations on public interfaces.
- Use Google-style docstrings for modules, classes, and public functions, consistent with current project conventions.
- Double quotes, 4-space indentation, imports at module scope.
- Prefer vectorized pandas/numpy operations for tabular calculations where appropriate.
- CI checks are non-mutating: `uv run ruff check .` and `uv run ruff format --check .`.

## 5. Logging & telemetry

- Use the project's operational logging conventions for human-readable diagnostics.
- Do not introduce a second logging framework as part of unrelated work.
- Structured trajectory telemetry under `src/core/telemetry/` is a separate machine-readable concern.
- Telemetry must fail open and must not alter business execution semantics.
- Never persist secrets in telemetry payloads.

When editing a legacy file that currently uses a different logging pattern, do not perform an unrelated logging migration unless the active task owns it.

## 6. TDD, verification & coverage

- Add or update focused tests with implementation changes.
- Run the relevant pytest suite before declaring work complete.
- Mock external APIs and local LLM endpoints in deterministic tests.
- Project target: ≥85% line coverage overall; new financial-analysis code should directly exercise meaningful branches and edge cases.
- Run the complete quality gate specified by the active milestone plan before completion.

## 7. Financial-analysis guardrails

- Deterministic financial math belongs in Python, never in the LLM.
- `docs/FINANCE_MATH.md` is the project authority for currently implemented/project-selected formula semantics.
- Preserve current Momentum semantics unless the task explicitly changes them.
- Historical-series data and current-market quotes are distinct capabilities. Do not implement a current quote by pretending a one-day historical download is a quote API when the active plan requires a first-class quote boundary.
- Missing financial data must be explicit; do not silently substitute zero.
- Do not add RSI, MACD, Sharpe, valuation models, or other algorithms merely because an older convenience document mentions them.

## 8. Heterogeneous strategy independence

- Select/implement analyzers according to the task, not according to which analyzer existed first.
- Do not treat Momentum as the universal financial-analysis shape.
- A new strategy may legitimately use different config fields, data inputs, and result metrics.
- Reuse `BaseAnalyzer` where sufficient; do not invent a parallel strategy framework speculatively.

## 9. OS, shell & execution

- Primary development environment: Windows 11 + PowerShell.
- Prefer portable path handling through `pathlib.Path`.
- Execute project tools through `uv run ...` from the repository root.
- Recommended local repair/check order:
  `uv run ruff check --fix .` → `uv run ruff format .` → type check → tests.

## 10. Human-in-the-loop gates

Require explicit user confirmation before:
- destructive file deletion;
- git reset/force-push;
- database migrations against user data;
- opening or merging PRs;
- structural repository changes not already authorized by the active implementation plan.

## 11. Context index

- Active milestone implementation → `docs/MILESTONE_v0_2_IMPLEMENTATION_PLAN.md`
- Roadmap → `docs/MASTER_PLAN.md`
- Rationale / decision history → `docs/DISCOVERY_WORKBOOK.md`
- Architecture → `docs/ARCHITECTURE.md`
- Financial mathematics → `docs/FINANCE_MATH.md`
- Domain terms → `docs/GLOSSARY.md`
- Hardware/model modes → `docs/HARDWARE.md`
- Convenience slash commands → `.claude/commands/` (lower authority than the documents above)
