"""Command Line Interface routing for the Financial Data Agents execution suite."""

import typer

from src.analysis.graham_value.graham_value_analyzer import (
    GrahamValueAnalyzer,
    GrahamValueConfig,
)
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
            adapter.info(f"SMA({config.short_window}): {_display_optional_metric(metrics.short_sma_val)}")
            adapter.info(f"SMA({config.long_window}): {_display_optional_metric(metrics.long_sma_val)}")
            adapter.info(f"Crossover Signal: {_display_optional_metric(metrics.crossover_signal)}")

    except DataFetchError as err:
        with logger_context as adapter:
            adapter.error(
                f"Market data retrieval failed: Ticker symbol '{ticker or analyzer._fallback_ticker}' "
                "appears to be invalid, unavailable, delisted, or returned no market data. "
                "Please verify the ticker symbol and try again."
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


def _display_optional_metric(value: float | None) -> str:
    """Render a transitional CLI metric without exposing non-finite sentinels."""
    return "unavailable" if value is None else f"{value:.2f}"


@app.command(name="graham")
def graham(
    ticker: str | None = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Target stock/asset ticker symbol (e.g., AAPL, KO)",
    ),
    eps: float = typer.Option(..., "--eps", "-e", help="TTM earnings per share (must be positive)"),
    expected_growth_rate: float = typer.Option(
        ...,
        "--expected-growth-rate",
        "-g",
        help="Expected annual growth rate in percent (e.g., 5.0 for 5 %)",
    ),
    current_aaa_yield: float = typer.Option(
        ...,
        "--current-aaa-yield",
        "-y",
        help="Current AAA corporate bond yield in percent (e.g., 5.25)",
    ),
    current_price: float | None = typer.Option(
        None,
        "--current-price",
        "-p",
        help="Optional explicit current market price; fetched via the data client when omitted",
    ),
) -> None:
    """Execute Benjamin Graham intrinsic value analysis with margin of safety."""
    with logger_context as adapter:
        adapter.info(f"Launching Graham valuation agent... [analysis_mode:graham, ticker:{ticker}]")

    analyzer = GrahamValueAnalyzer(default_ticker=ticker)

    try:
        config = GrahamValueConfig(
            eps=eps,
            expected_growth_rate=expected_growth_rate,
            current_aaa_yield=current_aaa_yield,
        )
        metrics = analyzer.run_analysis(config=config, ticker=ticker, current_price=current_price)

        with logger_context as adapter:
            adapter.info(f"Analysis Complete for {metrics.ticker}")
            adapter.info(f"TTM EPS: ${metrics.eps:,.2f}")
            adapter.info(f"Growth Rate (g): {metrics.expected_growth_rate:.2f}%")
            adapter.info(f"Intrinsic Value: ${metrics.intrinsic_value:,.2f}")
            if metrics.current_price is not None and metrics.margin_of_safety_percent is not None:
                adapter.info(f"Current Price: ${metrics.current_price:,.2f}")
                adapter.info(f"Margin of Safety: {metrics.margin_of_safety_percent:.2f}%")
            else:
                adapter.warning("Margin of Safety: unavailable (no current quote obtained)")

    except DataFetchError as err:
        with logger_context as adapter:
            adapter.error(f"Market data retrieval failed: {err}")
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
