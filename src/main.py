import sys

from src.core.telemetry import RunContext
from src.core.telemetry.run_context import set_current_run_context
from src.utils.logger_util import setup_global_logging, teardown_global_logging


def main() -> None:
    """Bootstrap the application and establish one identity for the CLI run."""
    run_context = RunContext.new()
    set_current_run_context(run_context)

    try:
        setup_global_logging()
    except Exception as e:
        print(f"Critical initialization failure: {e}", file=sys.stderr)
        sys.exit(1)

    from src.cli import app  # noqa: PLC0415

    try:
        app()
    finally:
        teardown_global_logging()


if __name__ == "__main__":
    main()
