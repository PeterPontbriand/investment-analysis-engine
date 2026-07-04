# Financial Data Agents Project

This repository builds autonomous Python agents for investment analysis using yfinance and local Large Language Models (LLMs).

**Core Goal:** Pull live or historical data → compute signals / backtests → generate reports/dashboards with zero manual coding after initial prompt. See CLAUDE.md for details.

## Jupyter Notebooks

To run an interactive data science notebook environment:

```bash
cd path/to/your/project
jupyter notebook
```

## Running the Application

The CLI is structured around subcommands. To run the a quantitative analysis, use the appropriate subcommand, e.g. `momentum`.

### Command Line Interface Syntax

To execute the momentum analysis agent:

```bash
# General Syntax
python -m src.main momentum [OPTIONS]

# Example: Run momentum analysis with default settings (BTC-USD)
python -m src.main momentum

# Example: Run analysis on a specific ticker with custom short and long windows
python -m src.main momentum --ticker AAPL --short-window 10 --long-window 30

# Example: Run analysis with custom worker thread allocations
python -m src.main momentum --threads 8

# View the auto-generated CLI parameter help menu
python -m src.main --help
python -m src.main momentum --help
```

## Testing

To run the complete cross-platform, asynchronous test suite with full coverage metrics:

```bash
uv run pytest tests/ --import-mode=importlib --cov=src --cov-report=html
# (Or simply pytest tests/... if the .venv is actively activated in the PowerShell session).

# For specific isolated sanity-check scenarios:
uv run --isolated pytest tests/ --import-mode=importlib --cov=src --cov-report=html
```

## Static type checking

To perform static type checking:

```bash
uv run python -m mypy --config-file ./.mypyrc src
```

## Linting

To run the Ruff linter:

```bash
ruff format . && ruff check --fix .
```

## Troubleshooting

If you encounter a `ModuleNotFoundError` when attempting to run local files directly, always ensure you invoke them as execution modules from the project root using the **`python -m`** flag prefix commands shown above.
