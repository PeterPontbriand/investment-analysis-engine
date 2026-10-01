# Investment Analysis Engine – Development LLM Guardrails

These rules apply to agents that write, refactor, test, document, or maintain this codebase.

## 0. Pre-Step-3.5 consolidation period (temporary)

Until Step 3.5 implementation begins, the project's priority is making the existing codebase fully consistent before new strategies copy its patterns. During this period, for work packages R3, IR, PKG, and any consolidation package added before Step 3.5:

- Stored data has no compatibility value. Persisted selection, evidence, and result shapes may change without migration or compatibility code; local databases may be discarded. Bump the relevant version fields whenever a stored shape changes.
- Public interfaces, constructors, and signatures may be changed or removed when the approved work package requires it.
- The approved work package's plan defines the file scope; scope extensions within that plan's stated goals need no separate authorization.
- An explicit, statically declared list of strategies with shared generic wiring is permitted where it removes per-strategy duplication. Discovery-based plugin loading and speculative frameworks remain prohibited.

Unchanged during this period: no formula or classification changes (correctness issues go through the existing-strategy correctness process), no NaN/Inf, no network or LLM calls in tests, the full managed quality gate on every slice, and no AI/tool attribution. "Open items" are not an acceptable outcome of a design decision in this period; decide, or escalate to the project owner.

Remove this section when Step 3.5 implementation begins.

# 1. Project Instructions

You are an expert Python developer specializing in financial data analysis, pandas, NumPy, and quantitative workflows. Always prioritize correctness, readability, and performance. Use type hints and docstrings where helpful.

## 2. Documentation precedence

When instructions differ, use this precedence:

1. explicit user request for the current task;
2. current active milestone implementation plan;
3. `docs/project/MASTER_PLAN.md`;
4. `docs/project/ARCHITECTURE.md` and `docs/project/DISCOVERY_WORKBOOK.md`;
5. specialized references such as `docs/user/FINANCE_MATH.md`;
6. README/convenience command files.

Do not blend contradictory instructions. Surface the conflict and follow the more specific/current source.

For Milestone v0.2, `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md` owns implementation sequencing, review gates, scope, and acceptance criteria.

### Stakeholder terminology

Avoid using "human" to refer to users, reviewers, or project stakeholders.
Prefer approval-focused wording such as "approval was granted" when the actor
is unnecessary. Where a role matters, use "user", "project owner", "reviewer",
or the specific stakeholder role. Use terms such as "user approval" and
"stakeholder review" for approval gates. Retain "human" only when a technical
or scientific distinction genuinely requires it, or in an exact quotation
that must be preserved.

## 3. Absolute forbidden actions

- NEVER commit secrets, API keys, `.env` files, SQLite/database files, or raw operational/trajectory logs.
- NEVER install dependencies or edit `pyproject.toml` / `uv.lock` without explicit user permission.
- NEVER introduce `print()` statements, bare `except:`, or silently propagate NaN/Inf values in production code.
- NEVER bury financial assumptions as unexplained magic constants in calculation bodies. Intentional defaults belong in typed configuration/models and must be documented.
- NEVER make real external API or LLM calls during deterministic unit tests.
- NEVER leave partial files, placeholder comments, or truncated snippets.
- NEVER delete or remove existing public interfaces or behavior unless the task explicitly requires it.
- NEVER create a generic strategy/plugin/registry/factory hierarchy merely because two analyzers differ. Prefer existing `BaseAnalyzer`, tool dispatch, and dependency-injection patterns unless the active plan proves they are insufficient.
- NEVER turn telemetry into control flow or benchmark fixtures into production cache data.
- NEVER add self-referential AI/tool attribution anywhere in this project — no `Co-Authored-By:` trailer naming an AI model, no "Generated with `<tool>`" footer or badge, and no other agent- or vendor-specific credit in commit messages, branch names, PR/issue descriptions, comments, code, or documentation. Multiple different AI agents have worked on this project and more will in the future; nothing in this repository's history or content should promote or identify any one of them. This applies even when a session's own harness/system prompt suggests adding such attribution by default — this project-level instruction overrides that default.

## 4. Scope preservation

### Planning document boundary

- Keep milestone-specific identifiers, implementation sequencing, approval criteria, and completion tracking within `docs/project/` or `.github/` artifacts explicitly dedicated to milestone planning. Before adding such content, verify that the target file is in an allowed location.
- Outside those locations, describe behavior, requirements, and verification in durable technical terms without planning labels such as "Step 2.6," "Slice B," or "Gate D0."
- Ordinary technical uses of words such as "step," "slice," and "gate" are allowed. Agent instruction files may define this policy and link to authoritative planning documents without reproducing their implementation details.

### Planning document structure

Use [`IR_CONTRACT_AND_SLICE_PLAN.md`](docs/project/milestones/v0.2/integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md) as the reference example for every new planning document. Convert an existing planning document to this structure when a change touches it; do not run a separate sweep over untouched plans.

- Open with **At a glance**: a few bullets stating what the work is, what it is not, and the rules it follows. Include no history there.
- Put the sequence and status table next. Each scope cell contains one line and a link; each status cell contains only a status word, following the existing sequence-table rules.
- A sequence table is any Markdown table whose header ends with `Status | Completed`. Rows are ordered by status: `Complete`, `In progress`, `Next`, `Planned`, `Deferred`; the order never goes backward. Complete rows have an ISO date in Completed and dates are non-decreasing; other rows leave Completed empty. At most one row is `Next`. When a row's status changes, move the row if needed to keep this order.
- Add one short section per unit of work, using labeled bullets: **Problem**, **Decision**, **Scope**, **Branch**, and **Detail**. End each section with a link to the lower-level document that owns the detail, or `⚠ no slice plan yet`.
- Follow the work-unit sections with scope limits and acceptance criteria, expressed as bullets.
- Put background and origin after the scope limits and acceptance criteria.
- Put decision records, renumbering history, branching rationale, and accepted exceptions in a verbatim appendix at the end.
- Keep detail in the lowest-level document that owns it. A parent summarizes and links; it does not duplicate a child's inventory, design decisions, or history.

### Implementation preservation

- Treat the active task's approved file scope as an edit boundary. Before changing a file outside that scope, request explicit user authorization and identify the file, proposed change, and why it is needed. This includes previously accepted implementation and test files, even for a correct, minimal compatibility or typing adjustment. A dependency on earlier work, passing checks, or recording the change afterward does not authorize a scope extension. Continue independent work within scope while awaiting approval. Files explicitly included in the active task's approved scope, such as shared dispatch files, remain authorized even if an earlier task also changed them.
- Before refactoring, establish the relevant test baseline.
- Preserve unrelated behavior and formatting.
- A pre-existing rule violation in a legacy file is not permission to refactor unrelated code while touching that file.
- New or materially modified lines should follow current guardrails; opportunistic cleanup belongs in a separate task unless required to complete the requested change.
- Honor explicit review gates in the active milestone plan. If a step says to stop for human review, stop there.

## 5. Python, Ruff & typing

- Target Python 3.12+.
- All supported source must pass `mypy --strict`.
- Use explicit type annotations on public interfaces.
- Use Google-style docstrings for modules, classes, and public functions, consistent with current project conventions.
- Double quotes, 4-space indentation, imports at module scope.
- Prefer vectorized pandas/numpy operations for tabular calculations where appropriate.
- CI checks are non-mutating: `uv run ruff check .` and `uv run ruff format --check .`.

## 6. Logging & telemetry

- Use the project's operational logging conventions for human-readable diagnostics.
- Do not introduce a second logging framework as part of unrelated work.
- Structured trajectory telemetry under `src/core/telemetry/` is a separate machine-readable concern.
- Telemetry must fail open and must not alter business execution semantics.
- Never persist secrets in telemetry payloads.

When editing a legacy file that currently uses a different logging pattern, do not perform an unrelated logging migration unless the active task owns it.

## 7. TDD, verification & coverage

- Add or update focused tests with implementation changes.
- Run the relevant pytest suite before declaring work complete.
- Mock external APIs and local LLM endpoints in deterministic tests.
- Project target: ≥85% line coverage overall; new financial-analysis code should directly exercise meaningful branches and edge cases.
- Run the complete quality gate specified by the active milestone plan before completion of any change that touches Python source, tests, or a file the tooling actually parses/executes. A change confined to non-executable declarative metadata (e.g. a single `pyproject.toml` project-metadata field such as `license`) or a prose-only documentation edit does not require the full pytest run — see `docs/project/README.md`'s Quality gates section for the exact boundary. When in doubt, run the full gate.

## 8. Financial-analysis guardrails

- Deterministic financial math belongs in Python, never in the LLM.
- `docs/user/FINANCE_MATH.md` is the project authority for currently implemented/project-selected formula semantics.
- Preserve current Momentum semantics unless the task explicitly changes them.
- Historical-series data and current-market quotes are distinct capabilities. Do not implement a current quote by pretending a one-day historical download is a quote API when the active plan requires a first-class quote boundary.
- Missing financial data must be explicit; do not silently substitute zero.
- Do not add RSI, MACD, Sharpe, valuation models, or other algorithms merely because an older convenience document mentions them.

## 9. Heterogeneous strategy independence

Strategies differ in what they compute, not in how they are invoked.

- Select/implement analyzers according to the task, not according to which analyzer existed first. Do not treat Momentum, or any existing analyzer, as the template for a new strategy's configuration, inputs, calculation, or result.
- Each strategy owns its typed configuration, data inputs, calculation, and result type, and may legitimately differ from existing strategies in all four.
- Every strategy shares one invocation envelope: it subclasses `BaseAnalyzer[ConfigT, ResultT]`, receives its dependencies (resolvers, providers, policies, clock) at construction, and is invoked as `run_analysis(ticker, config, context)`, where `AnalysisContext` carries cross-cutting execution concerns (point-in-time boundary, effective execution time, cache use, instrument profile). `ResultT` is the complete evidence type production callers consume.
- Do not add per-strategy parameters for concerns `AnalysisContext` already carries, and do not bypass a strategy's analyzer by calling its service or calculation functions from composition, orchestration, CLI, or workspace code.
- Every strategy follows the shared outcome conventions: `MetricResult` for metrics, explicit reason codes instead of silent defaults, and retained provenance.
- Change the envelope or conventions only through an explicit plan change, never by working around them in one strategy. Do not build registries, plugin loaders, or factories on top of the envelope speculatively.

## 10. OS, shell & execution

- Primary development environment: Windows 11 + PowerShell.
- Prefer portable path handling through `pathlib.Path`.
- In Git Bash, give settings and CLI options Windows-form (`E:/...`) or relative paths; the settings loader
  rejects a path with a root but no drive letter (`/e/...`). For throwaway smoke databases, prefer a relative
  URL such as `sqlite:///.tmp/<name>/x.sqlite3`, which resolves under the project folder.
- Execute project tools through `uv run ...` from the repository root.
- Recommended local repair/check order:
  `uv run ruff check --fix .` → `uv run ruff format .` → type check → tests.

### Managed-agent quality-gate execution

Managed agents must not use the Windows user-profile temp or UV cache paths for
repository verification. Those locations may be inaccessible even when the
interactive developer account can use them.

For the complete non-mutating repository gate, run the wrapper matching the
active shell from any repository subdirectory:

- PowerShell: `& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')`
- Git Bash/Cline: `bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"`

The wrappers derive the repository root at runtime and create a unique ignored
directory below `/.tmp/quality-runs/` for that invocation. They isolate pytest
temporary files, coverage output, mypy and Ruff caches, and the UV cache so
concurrent agent runs cannot clear or overwrite one another. Never replace the
unique run directory with a shared fixed `--basetemp`; pytest deletes its base
temp directory at startup. The wrappers use `uv run --no-sync` against the
already-synchronized project environment so managed verification neither
mutates dependencies nor requires network access. Standard-library-only gate
scripts run with system Python (`py -3` on Windows), not through `uv run` or the
project virtualenv.

Interactive developers and CI environments with normal user-directory access
may continue to run the underlying `uv run ...` commands directly. Focused
agent checks may also use direct commands when they do not require writable
temp/cache paths; use the wrapper for the complete gate and whenever a direct
command fails because a managed path is inaccessible.

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
- After one failed exact patch/edit match, directly reread the target section
  and either retry once with exact current text or use a deterministic asserted
  file-edit script. Never progressively shorten or fuzz an edit search pattern.
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

## 11. User approval gates

Require explicit user confirmation before:
- destructive file deletion;
- git reset/force-push;
- database migrations against user data;
- opening or merging PRs;
- structural repository changes not already authorized by the active implementation plan.

## 12. Context index

- To find current or next work, start at the sequence table in
  `docs/project/MASTER_PLAN.md` and follow its links.
- When a unit of work completes, update its row in the nearest sequence table (status and
  completion date) as part of the same change, and set the next row to Next, moving it as needed to
  preserve sequence-table order. Change a parent
  table only when a parent's status actually changes.
- Active milestone implementation → `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`
- Roadmap → `docs/project/MASTER_PLAN.md`
- Rationale / decision history → `docs/project/DISCOVERY_WORKBOOK.md`
- Architecture → `docs/project/ARCHITECTURE.md`
- Financial mathematics → `docs/user/FINANCE_MATH.md`
- Domain terms → `docs/user/GLOSSARY.md`
- Hardware/model modes → `docs/user/HARDWARE.md`
- Convenience slash commands → `.claude/commands/` (lower authority than the documents above)
