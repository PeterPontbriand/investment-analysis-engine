"""Command Line Interface routing for the Financial Data Agents execution suite."""

import typer

from src.analysis.momentum.momentum_analyzer import MomentumAnalyzer, MomentumConfig
from src.core.telemetry import RunContext
from src.core.telemetry.run_context import get_current_run_context, set_current_run_context
from src.data.base_client import DataFetchError
from src.utils.logger_util import setup_logger

app = typer.Typer(help="Financial Data Agents Command Line Interface")
logger_context = setup_logger("cli_runtime")


@app.callback()
def main_entry_point() -> None:
    """Initialize one RunContext for this CLI invocation if main.py did not."""
    if get_current_run_context() is None:
        set_current_run_context(RunContext.new())


def get_cli_run_context() -> RunContext:
    """Return the explicit execution identity for the current CLI invocation."""
    context = get_current_run_context()
    if context is None:
        raise RuntimeError("CLI RunContext has not been initialized.")
    return context


@app.command(name="momentum")
def momentum(
    ticker: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Target stock/asset ticker symbol (e.g., AAPL, BTC-USD)",
    ),
    short_window: int | None = typer.Option(None, "--short-window", "-s", help="Moving average short window size"),
    long_window: int | None = typer.Option(None, "--long-window", "-l", help="Moving average long window size"),
    threads: int = typer.Option(4, "--threads", help="Worker thread count allocated to concurrent jobs"),
) -> None:
    """Execute quantitative momentum strategy analysis over historical market metrics."""
    with logger_context as adapter:
        adapter.info(f"Launching momentum analysis agent... [analysis_mode:momentum, worker_threads:{threads}]")

    analyzer = MomentumAnalyzer(default_ticker=ticker)

    try:
        config_args = {}
        if short_window is not None:
            config_args["short_window"] = short_window
        if long_window is not None:
            config_args["long_window"] = long_window

        config = MomentumConfig(**config_args)
        metrics = analyzer.run_analysis(config=config, ticker=ticker)

        with logger_context as adapter:
            adapter.info(f"Analysis Complete for {metrics.ticker}")
            adapter.info(f"Current Price: ${metrics.current_price:,.2f}")
            adapter.info(f"Trend Status: {metrics.status.name}")
            adapter.info(f"SMA({config.short_window}): {metrics.short_sma_val:.2f}")
            adapter.info(f"SMA({config.long_window}): {metrics.long_sma_val:.2f}")
            adapter.info(f"Crossover Signal: {metrics.crossover_signal}")

    except DataFetchError as err:
        with logger_context as adapter:
            adapter.error(
                f"Market data retrieval failed: Ticker symbol '{ticker or analyzer._fallback_ticker}' "
                "appears to be delisted, invalid, or returned empty data. "
                "Please verify the ticker spelling and try again."
            )
        raise typer.Exit(code=1) from err

    except ValueError as err:
        with logger_context as adapter:
            adapter.error(f"Validation constraints breached: {err}")
        raise typer.Exit(code=1) from err

    except Exception as err:
        with logger_context as adapter:
            adapter.error(f"An unexpected error occurred during execution: {err}")
        raise typer.Exit(code=1) from err


if __name__ == "__main__":
    app()
