import logging
import sys

from src.core.settings_error import SettingsEnvironmentError

try:
    # The settings are built when this module loads, and many modules read them on import. A bad engine
    # variable is therefore reported here, before any other project import, as one sentence and no traceback.
    # Logging is configured from these same settings, so it is not up yet and the sentence is not logged.
    import src.config  # noqa: F401
except SettingsEnvironmentError as error:
    print(error, file=sys.stderr)
    sys.exit(2)

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
    except Exception:
        # Typer replaces the interpreter's exception hook and shows its own traceback on standard error, so
        # the log file would otherwise never learn of an exception that no command handled.
        logging.getLogger("system.crash").critical("Uncaught exception encountered.", exc_info=True)
        raise
    finally:
        teardown_global_logging()


if __name__ == "__main__":
    main()
