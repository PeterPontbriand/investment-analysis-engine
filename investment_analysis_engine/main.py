import logging
import sys

from investment_analysis_engine.core.settings_error import SettingsEnvironmentError, StrategySettingsError

try:
    # The settings are built when this module loads, and many modules read them on import. A bad engine
    # variable is therefore reported here, before any other project import, as a one-sentence message and no traceback.
    # Logging is configured from these same settings, so it is not up yet and the message is not logged.
    import investment_analysis_engine.config  # noqa: F401
except SettingsEnvironmentError as error:
    print(error, file=sys.stderr)
    sys.exit(2)

from investment_analysis_engine.telemetry.run_context import RunContext, set_current_run_context
from investment_analysis_engine.utils.logger_util import setup_global_logging, teardown_global_logging


def main() -> None:
    """Bootstrap the application and establish one identity for the CLI run."""
    run_context = RunContext.new()
    set_current_run_context(run_context)

    try:
        setup_global_logging()
    except Exception as e:
        print(f"Critical initialization failure: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        from investment_analysis_engine.cli import app  # noqa: PLC0415
    except StrategySettingsError as error:
        # A strategy's settings file is read when the commands are defined, so a bad file stops every command
        # here, with the engine-settings handling above: one message on standard error and no traceback.
        print(error, file=sys.stderr)
        teardown_global_logging()
        sys.exit(2)

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
