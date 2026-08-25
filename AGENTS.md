# Financial Data Agents – Development LLM Guardrails

These rules apply to agents that write, refactor, test, document, or maintain this codebase.

## 1. Documentation precedence

When instructions differ, use this precedence:

1. explicit human request for the current task;
2. current active milestone implementation plan;
3. `docs/project/MASTER_PLAN.md`;
4. `docs/project/ARCHITECTURE.md` and `docs/project/DISCOVERY_WORKBOOK.md`;
5. specialized references such as `docs/user/FINANCE_MATH.md`;
6. README/convenience command files.

Do not blend contradictory instructions. Surface the conflict and follow the more specific/current source.

For Milestone v0.2, `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md` owns implementation sequencing, review gates, scope, and acceptance criteria.

## 2. Absolute forbidden actions

- NEVER commit secrets, API keys, `.env` files, SQLite/database files, or raw operational/trajectory logs.
- NEVER install dependencies or edit `pyproject.toml` / `uv.lock` without explicit user permission.
- NEVER introduce `print()` statements, bare `except:`, or silently propagate NaN/Inf values in production code.
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
- `docs/user/FINANCE_MATH.md` is the project authority for currently implemented/project-selected formula semantics.
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

### Repository search & file inspection

Use the simplest search mechanism that matches the question. A search that
returns no matches is information, not a reason to repeatedly invent more
complex patterns.

- If the exact file is known, read that file directly before searching.
- For exact text, Markdown links, identifiers, headings, paths, CLI flags, or
  punctuation-heavy strings, prefer a **literal search**, not a regular
  expression.
- Treat strings containing Markdown or code punctuation such as `#`, `[`, `]`,
  `(`, `)`, backticks, `/`, `\`, `_`, `*`, `+`, `?`, or `.` as literal by
  default unless regex semantics are explicitly required.
- On Windows/PowerShell, prefer:
  `Select-String -SimpleMatch '<literal text>'`
  for exact text searches.
- For a repository-wide literal Markdown search, prefer a simple pipeline such
  as:
  `Get-ChildItem -Recurse -Filter *.md | Select-String -SimpleMatch 'GLOSSARY.md#'`
  rather than constructing a speculative regex.
- Use regex only when the task genuinely requires pattern matching. Start with
  the smallest regex that can work and escape literal punctuation correctly.
- Do not retry a failing/no-match search by making the pattern progressively
  more elaborate without first verifying:
  1. the target file/path exists;
  2. the expected text actually appears in a directly inspected file; and
  3. the search tool is interpreting the pattern as literal text or regex as
     intended.
- After one unexpected no-match result, inspect a likely file directly or use a
  simpler literal search. After two no-match attempts, stop changing patterns
  and reassess the search assumption.
- When auditing links or references, enumerate the source material first
  (for example, headings and literal links), then compare the resulting lists.
  Do not try to encode the entire audit into one complex search expression.
- Never interpret "no search matches" as proof that a file or concept does not
  exist when direct file inspection is available.

### Non-interactive commands and pagers

Agent-run shell commands must be safe for non-interactive execution. Do not
invoke commands that may wait for pager input, editor input, confirmation, or
other interactive terminal state unless the task explicitly requires it.

For Git commands that can invoke a pager, explicitly disable paging:

- use `git --no-pager diff` instead of `git diff`;
- use `git --no-pager log ...` instead of `git log ...`;
- use `git --no-pager show ...` instead of `git show ...`;
- use `git --no-pager branch ...` when branch output may page.
- Commands run by an agent should be non-interactive and bounded by default;
  explicitly disable pagers and avoid prompts that require terminal input.

Prefer per-command pager suppression rather than changing the user's global Git
configuration.

Examples:

```powershell
git --no-pager diff
git --no-pager diff --stat
git --no-pager diff -- path/to/file
git --no-pager log -10 --oneline
git --no-pager show --stat HEAD
```

For large output, do not dump an unbounded repository-wide result merely because
paging has been disabled. Narrow the command first:

1. inspect `--stat`, `--name-only`, or `--name-status`;
2. identify the relevant files;
3. inspect targeted diffs or bounded log history.

Do not use `less`, `more`, `Out-Host -Paging`, or another pager in agent-driven
commands.

If a command unexpectedly enters a pager or other interactive state:

1. exit it once (`q` for common Git pagers);
2. do not rerun the same command unchanged;
3. rerun it in explicitly non-interactive form, normally with `git --no-pager`
   or a narrower bounded command.

A tool appearing to hang after producing output should be treated as a possible
pager/interactive-state problem before assuming the underlying command failed.

## 10. Human-in-the-loop gates

Require explicit user confirmation before:
- destructive file deletion;
- git reset/force-push;
- database migrations against user data;
- opening or merging PRs;
- structural repository changes not already authorized by the active implementation plan.

## 11. Context index

- Active milestone implementation → `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`
- Roadmap → `docs/project/MASTER_PLAN.md`
- Rationale / decision history → `docs/project/DISCOVERY_WORKBOOK.md`
- Architecture → `docs/project/ARCHITECTURE.md`
- Financial mathematics → `docs/user/FINANCE_MATH.md`
- Domain terms → `docs/user/GLOSSARY.md`
- Hardware/model modes → `docs/user/HARDWARE.md`
- Convenience slash commands → `.claude/commands/` (lower authority than the documents above)
