"""The ``serve`` command: run the local HTTP interface until standard input closes.

The command validates its options, checks that the database is ready, binds its own loopback socket, and hands that
socket to uvicorn. It writes one JSON line holding the port and the per-launch bearer token to standard output once
uvicorn reports that it has started, and exits when standard input reaches end of file or on Ctrl+C. Every launch
failure is a failure envelope on standard output and exit code 1.
"""

import json
import logging
import os
import secrets
import socket
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from types import FrameType
from typing import Annotated, NoReturn, Protocol

import typer
import uvicorn

from investment_analysis_engine.api.app import create_app, refresh_jobs_of
from investment_analysis_engine.api.origins import normalize_origin
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.database import open_database
from investment_analysis_engine.cli_database_target import file_backed_settings
from investment_analysis_engine.cli_support import report_failure
from investment_analysis_engine.core.failure_classification import classify_failure
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.reporting.failure_envelope import failure_envelope

logger = logging.getLogger(__name__)

LOOPBACK_ADDRESS = "127.0.0.1"
"""The only address the server binds."""

MAX_PORT = 65535
"""The highest port number."""

GRACEFUL_SHUTDOWN_SECONDS = 5
"""How long a request in flight, and a refresh job running, may take to finish once the server is asked to stop."""

_STDIN_CHUNK = 4096


class _AnnouncingServer(uvicorn.Server):
    """A uvicorn server that runs a callback once its startup has completed, and another when it is asked to stop."""

    def __init__(
        self, config: uvicorn.Config, *, on_started: Callable[[], None], on_stopping: Callable[[], None]
    ) -> None:
        """Keep the callbacks that announce a completed startup and a request to stop."""
        super().__init__(config)
        self._on_started = on_started
        self._on_stopping = on_stopping

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        """Tell the callback that the server is stopping, then let uvicorn begin to stop (Ctrl+C or a signal)."""
        self._on_stopping()
        super().handle_exit(sig, frame)

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        """Start serving, then run the callback; a startup that failed does not announce."""
        await super().startup(sockets=sockets)
        if self.started:
            self._on_started()


def _fail(code: FailureReasonCode, message: str) -> NoReturn:
    """Write a launch failure's envelope to standard output and exit 1."""
    report_failure(failure_envelope(code, message), json_output=True)


@contextmanager
def _launch_failures() -> Iterator[None]:
    """Report an exception raised while launching as a failure envelope on standard output and exit 1.

    An exception that declares its own failure code keeps its message; any other is an ``execution_error`` with one
    fixed message, and its detail and traceback go to the log.
    """
    try:
        yield
    except (typer.Exit, typer.Abort):
        raise
    except Exception as exc:
        if isinstance(getattr(exc, "reason_code", None), FailureReasonCode):
            report_failure(failure_envelope(classify_failure(exc).reason_code, str(exc), cause=exc), json_output=True)
        logger.exception("Unexpected failure while launching 'ian serve'.")
        _fail(FailureReasonCode.EXECUTION_ERROR, "serve failed unexpectedly.")


def _allowed_origins(values: Sequence[str]) -> tuple[str, ...]:
    """Return the normalized ``--allow-origin`` values, rejecting any that is not ``scheme://host[:port]``."""
    origins: list[str] = []
    for value in values:
        canonical = normalize_origin(value)
        if canonical is None:
            raise InvalidParameterError(
                f"--allow-origin {value!r} must be scheme://host or scheme://host:port, with no path; "
                "* and null are not accepted.",
                parameters=("--allow-origin",),
            )
        origins.append(canonical)
    return tuple(dict.fromkeys(origins))


def _bind_loopback(port: int) -> socket.socket:
    """Bind a listening socket on the loopback address, or exit 1 with ``port_unavailable``."""
    if not 0 <= port <= MAX_PORT:
        raise InvalidParameterError(f"--port must be between 0 and {MAX_PORT}.", parameters=("--port",))
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((LOOPBACK_ADDRESS, port))
        listener.listen()
    except OSError as exc:
        listener.close()
        logger.warning("Could not bind %s:%d: %s", LOOPBACK_ADDRESS, port, exc)
        _fail(FailureReasonCode.PORT_UNAVAILABLE, f"Port {port} on {LOOPBACK_ADDRESS} is not available.")
    return listener


def _stop_when_stdin_closes(server: uvicorn.Server, on_stopping: Callable[[], None]) -> None:
    """Read standard input to its end, then tell the callback that the server is stopping and ask it to stop."""
    try:
        stream = getattr(sys.stdin, "buffer", None)
        if stream is not None:
            while stream.read(_STDIN_CHUNK):
                pass
    except (OSError, ValueError):
        logger.debug("Standard input could not be read; stopping the server.", exc_info=True)
    on_stopping()
    server.should_exit = True


class StoppableJobs(Protocol):
    """What the stop of the server needs from the refresh job: to cancel it, and to wait for its thread."""

    def begin_shutdown(self) -> None:
        """Cancel the job if it is running."""
        ...

    def wait_for_job(self, timeout: float) -> bool:
        """Wait up to ``timeout`` seconds for the job's thread to end; return whether it has."""
        ...


class _ShutdownClock:
    """Remembers when the server was first asked to stop, so the refresh job's grace runs beside uvicorn's.

    A refresh job gets :data:`GRACEFUL_SHUTDOWN_SECONDS` from the moment the stop begins, the same as a request in
    flight, so the grace is not spent after uvicorn's own.
    """

    def __init__(self, jobs: StoppableJobs, clock: Callable[[], float] = time.monotonic) -> None:
        """Keep the jobs whose cancellation a stop sets and the clock that times the grace."""
        self._jobs = jobs
        self._clock = clock
        self._lock = threading.Lock()
        self._began: float | None = None

    def begin(self) -> None:
        """Note that the server is stopping and set the running job's cancellation at once; later calls do nothing."""
        with self._lock:
            if self._began is not None:
                return
            self._began = self._clock()
        self._jobs.begin_shutdown()

    def remaining(self) -> float:
        """Return the seconds left of the grace; the whole of it if no stop was noted."""
        with self._lock:
            began = self._clock() if self._began is None else self._began
        return max(0.0, GRACEFUL_SHUTDOWN_SECONDS - (self._clock() - began))


def finish_refresh_job(jobs: StoppableJobs, shutdown: _ShutdownClock, *, exit_process: Callable[[int], object]) -> None:
    """Wait out the rest of the refresh job's grace; if the job's thread is still alive, end the process.

    A ``ThreadPoolExecutor`` worker holds up the interpreter's exit until its call returns, nothing times out a
    provider fetch, and a coordinator still alive at exit could save a run after the grace. So a job that has not
    ended is abandoned: one line says its unfinished jobs were not saved, logging is flushed and the process ends with
    ``exit_process(0)`` at once. A job that ended, or no job, does nothing.

    Args:
        jobs: The server's latest job.
        shutdown: When the stop began, which says how much of the grace is left.
        exit_process: Ends the process at once with an exit code, as ``os._exit`` does; a test supplies its own.
    """
    if jobs.wait_for_job(shutdown.remaining()):
        return
    logger.warning("The refresh did not finish before the server stopped; its unfinished jobs were not saved.")
    logging.shutdown()
    exit_process(0)


def _announce(port: int, token: str) -> None:
    """Write the ready line: the port and the token, as one line of JSON."""
    sys.stdout.write(json.dumps({"port": port, "token": token}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def serve(
    *,
    port: Annotated[int, typer.Option("--port", help="Loopback port to listen on; 0 lets the system choose.")] = 0,
    allow_origin: Annotated[
        list[str] | None,
        typer.Option("--allow-origin", help="An origin allowed to call the API, as scheme://host[:port]; repeatable."),
    ] = None,
    database_url: Annotated[str | None, typer.Option(help="Override the configured SQLite target.")] = None,
) -> None:
    """Serve the read API on loopback until standard input closes.

    Once the server is listening it writes one JSON line holding the port and a bearer token to standard output.
    """
    with _launch_failures():
        origins = _allowed_origins(allow_origin or [])
        selected = file_backed_settings(database_url)
        context = ApplicationContext(settings=selected)
        with open_database(context):
            pass
        listener = _bind_loopback(port)
    token = secrets.token_urlsafe(32)
    bound_port = int(listener.getsockname()[1])
    app = create_app(context=context, token=token, port=bound_port, allowed_origins=origins)
    config = uvicorn.Config(
        app,
        log_config=None,
        access_log=False,
        server_header=False,
        lifespan="off",
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
    )
    jobs = refresh_jobs_of(app)
    shutdown = _ShutdownClock(jobs)
    server = _AnnouncingServer(config, on_started=lambda: _announce(bound_port, token), on_stopping=shutdown.begin)
    threading.Thread(
        target=_stop_when_stdin_closes, args=(server, shutdown.begin), name="serve-stdin", daemon=True
    ).start()
    try:
        server.run(sockets=[listener])
    except KeyboardInterrupt:
        logger.info("Interrupted; the server has stopped.")
    finally:
        listener.close()
    shutdown.begin()
    finish_refresh_job(jobs, shutdown, exit_process=os._exit)


def register(app: typer.Typer) -> None:
    """Register the ``serve`` command on the root Typer app."""
    app.command(name="serve")(serve)


__all__ = ["register", "serve"]
