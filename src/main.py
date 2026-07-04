import sys

from src.utils.logger_util import setup_global_logging, teardown_global_logging


def main() -> None:
    """Bootstrap the application and hand off execution to the CLI parser."""
    try:
        # Initialize background thread queue logging pipelines before application entry
        setup_global_logging()
    except Exception as e:
        print(f"Critical initialization failure: {e}", file=sys.stderr)
        sys.exit(1)

    # Delayed local import to break circular parsing dependencies across sub-commands
    from src.cli import app  # noqa: PLC0415

    try:
        # Typer reads sys.argv natively and delegates routing maps
        app()
    finally:
        # Guarantee memory queue items are completely flushed to disk on shutdown or crashes
        teardown_global_logging()


if __name__ == "__main__":
    main()
