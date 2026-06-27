# Preservation and Defensive Refactoring Skill

## Description
Enforces code preservation rules during bug resolution and prevents accidental removal of existing functionality.

## Scope
project-local

## Instructions
When resolving bugs, modifying logic, or refactoring Python scripts, you must adhere to these absolute boundaries:

1. **Strict Preservation**: Never delete, comment out, or omit an existing function, helper utility, variable assignment, or class method unless explicitly instructed to remove that feature.
2. **Defensive Modification**: If a block of code needs a bug fix, only modify the specific line causing the failure. Leave surrounding code, imports, and docstrings structurally intact.
3. **No Placeholders**: Do not use `# ... existing code ...` or pass placeholders inside files. Always output the complete function block showing the fix integrated seamlessly with the surrounding code.
4. **Regression Awareness**: Ensure that fixing a bug does not eliminate performance logic, error handling hooks, or logging layers built into the existing file context.

# Preservation and Strict Linting Compliance Skill

## Description
Enforces defensive programming habits and 100% compliance with strict Ruff code quality rules (D, ANN, B categories).

## Scope
project-local

## Instructions
When writing or refactoring Python code, you must adhere to these exact syntactic patterns to ensure zero Ruff linter errors:

1. **Strict Docstrings (D400, D415)**: 
   * Every function, method, and class must have a docstring.
   * The first line of a docstring MUST end with a period (`.`), exclamation mark (`!`), or question mark (`?`). No exceptions.
   * *Example:* `"""Calculate the exponential moving average."""`

2. **Full Type Annotations (ANN201, ANN202)**:
   * Every function definition must include an explicit return type annotation.
   * Public functions: `def calculate_rsi(data: list[float]) -> list[float]:`
   * Private/Helper functions: `def _smooth(value: float) -> float:`
   * If a function returns nothing, explicitly annotate it as `-> None`.

3. **Loop Variable Discipline (B007)**:
   * If a loop variable is declared but intentionally not accessed inside the loop block, you must prefix it with an underscore.
   * *Incorrect:* `for i in range(10): self.ping()`
   * *Correct:* `for _i in range(10): self.ping()`
