# /refactor-modernize

**Purpose:** Modernize code within an explicitly requested scope while preserving behavior.

## Instructions

- Read `AGENTS.md` and the active milestone plan first.
- Establish the relevant test baseline.
- Apply project Ruff conventions; do not introduce Black as a separate formatter.
- Add/improve type annotations and typed boundary models only where required by the task.
- Preserve public behavior and avoid unrelated architectural refactors.
- A legacy rule violation is not permission to clean up the entire file.
- Do not create new strategy/provider/plugin frameworks speculatively.
- Update focused tests and documentation when behavior/contracts change.
- Verify with the relevant `uv run ruff`, `mypy --strict`, and pytest commands.
