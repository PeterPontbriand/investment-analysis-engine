"""Command Line Interface routing for the Financial Data Agents execution suite."""

import typer

from src.analysis.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig
from src.data.base_client import DataFetchError
from src.utils.logger_util import setup_logger

# Initialize Typer application CLI
app = typer.Typer(help="Financial Data Agents Command Line Interface")
logger_context = setup_logger("cli_runtime")


@app.callback()
def main_entry_point() -> None:
    """Financial Data Platform CLI initialization layer."""
    pass


@app.command(name="momentum")
def momentum(
    ticker: str | None = typer.Option(
        None, "--ticker", "-t", help="Target stock/asset ticker symbol (e.g., AAPL, BTC-USD)"
    ),
    short_window: int | None = typer.Option(None, "--short-window", "-s", help="Moving average short window size"),
    long_window: int | None = typer.Option(None, "--long-window", "-l", help="Moving average long window size"),
    threads: int = typer.Option(4, "--threads", help="Worker thread count allocated to concurrent jobs"),
) -> None:
    """Execute quantitative momentum strategy analysis over historical market metrics."""
    with logger_context as adapter:
        adapter.info(f"Launching momentum analysis agent... [analysis_mode:momentum, worker_threads:{threads}]")

    # Initialize the strategy calculation block
    analyzer = MomentumAnalyzer(default_ticker=ticker)

    try:
        # Resolve config overrides
        config_args = {}
        if short_window is not None:
            config_args["short_window"] = short_window
        if long_window is not None:
            config_args["long_window"] = long_window

        config = MomentumConfig(**config_args)

        # Compute signals
        metrics = analyzer.run_analysis(config=config, ticker=ticker)

        # Log clean human-readable output status
        with logger_context as adapter:
            adapter.info(f"Analysis Complete for {metrics.ticker}")
            adapter.info(f"Current Price: ${metrics.current_price:,.2f}")
            adapter.info(f"Trend Status: {metrics.status.name}")
            adapter.info(f"SMA({config.short_window}): {metrics.short_sma_val:.2f}")
            adapter.info(f"SMA({config.long_window}): {metrics.long_sma_val:.2f}")
            adapter.info(f"Crossover Signal: {metrics.crossover_signal}")

    except DataFetchError as err:
        # Polished, consumer-friendly notification for invalid/delisted tickers
        with logger_context as adapter:
            adapter.error(
                f"Market data retrieval failed: Ticker symbol '{ticker or analyzer._fallback_ticker}' "
                "appears to be delisted, invalid, or returned empty data. "
                "Please verify the ticker spelling and try again."
            )
        raise typer.Exit(code=1) from err

    except ValueError as err:
        # True configuration/math boundary validation breaches (e.g., short_window >= long_window)
        with logger_context as adapter:
            adapter.error(f"Validation constraints breached: {err}")
        raise typer.Exit(code=1) from err

    except Exception as err:
        # Fallback boundary catch
        with logger_context as adapter:
            adapter.error(f"An unexpected error occurred during execution: {err}")
        raise typer.Exit(code=1) from err


if __name__ == "__main__":
    app()
