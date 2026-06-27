import sys

from src.utils.logger_util import setup_global_logging


def main() -> None:
    """Bootstrap the application and hand off execution to the CLI parser."""
    try:
        setup_global_logging()
    except Exception as e:
        print(f"Critical initialization failure: {e}", file=sys.stderr)
        sys.exit(1)

    # Delayed import to avoid circular dependency trees
    from src.cli import app  # noqa: PLC0415

    app()


if __name__ == "__main__":
    main()
