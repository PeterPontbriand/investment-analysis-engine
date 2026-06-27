# Financial Data Agents Project

This repository builds autonomous Python agents for ETF / momentum investment analysis using Massive.com and yfinance. Core goal: Pull live or historical data → compute momentum signals / backtests → generate reports/dashboards with zero manual coding after initial prompt. See CLAUDE.md for details.

## Jupyter Notebooks

To run an interactive data science notebook environment:

```bash
cd path/to/your/project
jupyter notebook
```

## Running the Application

### Module Entry Point
To execute the baseline analytical process script framework as a module:

```bash
# General Syntax
python -m src.typer_main [OPTIONS] DATASET

# Example: Run analysis on a data file using default parameters
python -m src.typer_main mock_dataset.csv

# Example: Run analysis with custom worker thread allocations
python -m src.typer_main mock_dataset.csv --threads 8

# View the auto-generated CLI parameter help menu
python -m src.typer_main --help
```

## Testing

To run the complete cross-platform, asynchronous test suite with full coverage metrics:

```bash
uv run pytest -v --cov=src tests/
```

## Static type checking
To perform static type checking:

```bash
uv run python -m mypy --config-file ./.mypyrc src
```

## Troubleshooting

If you encounter a `ModuleNotFoundError` when attempting to run local files directly, always ensure you invoke them as execution modules from the project root using the **`python -m`** flag prefix commands shown above.
