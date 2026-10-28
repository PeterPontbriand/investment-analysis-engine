import io
import logging
import sys

from investment_analysis_engine.core.settings_error import ComponentSettingsError, SettingsEnvironmentError


def use_utf8_output(*streams: object) -> None:
    """Write each of ``streams`` that is a text stream as UTF-8, whatever encoding Python chose for it.

    When output is redirected on Windows, Python 3.12 to 3.14 encodes it with the ANSI code page (cp1252), and a
    character outside that code page, such as the arrow in a help text, raises ``UnicodeEncodeError``. Python 3.15 makes
    UTF-8 the default; this gives every supported version the same behaviour. Only the encoding changes, so each
    stream keeps its error handler. A missing stream (``None``) and an object that is not a text wrapper, such as a
    stream a test captures, are left alone.

    Args:
        *streams: The streams to switch, normally standard output and standard error.
    """
    for stream in streams:
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def main() -> None:
    """Bootstrap the application and establish one identity for the CLI run."""
    # Nothing is written before this, so the settings-error message below is encoded as UTF-8 as well.
    use_utf8_output(sys.stdout, sys.stderr)

    try:
        # The settings are built when this module loads, and many modules read them on import. A bad engine
        # variable is therefore reported here, before any other project import, as a one-sentence message and no
        # traceback. Logging is configured from these same settings, so it is not up yet and the message is not
        # logged.
        import investment_analysis_engine.config  # noqa: F401, PLC0415
    except SettingsEnvironmentError as error:
        print(error, file=sys.stderr)
        sys.exit(2)

    from investment_analysis_engine.telemetry.run_context import (  # noqa: PLC0415
        RunContext,
        set_current_run_context,
    )
    from investment_analysis_engine.utils.logger_util import (  # noqa: PLC0415
        setup_global_logging,
        teardown_global_logging,
    )

    run_context = RunContext.new()
    set_current_run_context(run_context)

    try:
        setup_global_logging()
    except Exception as e:
        print(f"Critical initialization failure: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        from investment_analysis_engine.cli import app  # noqa: PLC0415
    except ComponentSettingsError as error:
        # A strategy's or provider's settings file is read when the commands are defined, so a bad file stops every
        # command here, with the engine-settings handling above: one message on standard error and no traceback.
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
