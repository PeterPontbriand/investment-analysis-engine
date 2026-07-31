# Financial Data Agents Project

This repository builds autonomous Python agents for investment analysis using yfinance and local Large Language Models (LLMs).

**Core Goal:** Pull live or historical data → compute signals / backtests → generate reports/dashboards with zero manual coding after initial prompt. See CLAUDE.md for details.

> **Execution Note:** Unless specified otherwise, execute all commands from the **project root directory** (`financial-data-agents/`).

---

## Jupyter Notebooks

To run an interactive data science notebook environment:

```bash
uv run jupyter notebook
```

---

## Running the Application

The CLI is structured around subcommands. To execute quantitative analysis modules:

```bash
# General Syntax
uv run financial-agents momentum [OPTIONS]

# Example: Run momentum analysis with default settings (BTC-USD)
uv run financial-agents momentum

# Example: Run analysis on a specific ticker with custom short and long windows
uv run financial-agents momentum --ticker AAPL --short-window 10 --long-window 30

# Example: Run analysis with custom worker thread allocations
uv run financial-agents momentum --threads 8

# View the auto-generated CLI parameter help menu
uv run financial-agents --help
uv run financial-agents momentum --help
```

*Note: If executing python modules directly without project entry point scripts, use the python module syntax from root:*
```bash
uv run python -m src.main momentum
```

---

## Testing

To run the complete cross-platform test suite with coverage metrics:

```bash
# Run full test suite
uv run pytest tests/ --import-mode=importlib --cov=src --cov-report=html

# Run core orchestration layer tests only
uv run pytest tests/core/

# For isolated pre-commit / CI sanity checks:
uv run --isolated pytest tests/ --import-mode=importlib --cov=src --cov-report=html
```

---

## Static Type Checking

To perform static type checking:

```bash
uv run python -m mypy --config-file ./.mypyrc src
```

---

## Linting & Formatting

To check, fix, and format code using Ruff:

```bash
uv run ruff check --fix . && uv run ruff format .
```