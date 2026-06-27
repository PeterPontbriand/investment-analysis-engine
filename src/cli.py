import typer

from src.utils.logger_util import setup_logger

app = typer.Typer()


@app.command()
def analyze(
    dataset: str = typer.Argument(..., help="Path to the data file"),
    threads: int = typer.Option(4, help="Number of worker threads"),
) -> None:
    """Run heavy multi-threaded data calculations."""
    # Retrieve the configured logger wrapper context
    logger_context = setup_logger("analysis")

    # Enter the context to obtain the properly configured contextual adapter
    with logger_context as adapter:
        # Bind operational metadata attributes directly onto the adapter instance
        adapter.set_extra({"target_dataset": dataset})
        adapter.info(f"Starting data array processing with {threads} workers...")

        # Launch your multithreaded analysis code here


if __name__ == "__main__":
    app()
