"""Attribute yfinance's SQLite connection leak in the live checks, and excuse that leak only.

Why live runs need this. yfinance keeps its caches in peewee SQLite databases. peewee holds one
``sqlite3.Connection`` per thread and closes it only from an ``atexit`` hook on the main thread. The Yahoo check
runs each request in a daemon worker thread (``_call_with_timeout`` in ``provider_checks.py``), so every check
leaves connections that nothing closes. On Python 3.13 and later an unclosed connection raises a
``ResourceWarning`` when it is freed, and the suite turns that warning into an error, so the leak fails whichever
live test happens to be running when the connection is freed (in the logged run, the SEC check).

Why a warning filter cannot excuse it. The warning names the code running when the object is freed, not the code
that allocated it, so a filter cannot tell yfinance's leak from a leak in this project. The allocating code is
known only from ``tracemalloc``, which this module starts with 25 frames (the depth ``PYTHONTRACEMALLOC=25``
gives, as the testing guidance prescribes). A wrapped ``sys.unraisablehook`` looks up the leaked object's
allocation traceback and excuses it only when yfinance allocated it through its peewee cache (rule below).

Why the strict gate is unchanged elsewhere. The hook is installed by a session fixture that exists only in
``tests/live``, so it runs only when live tests run. The default suite and the managed gate never collect a
live test and keep failing on every leak. Anything this hook does not recognise goes, unchanged, to the hook it wraps.

Tracking issue: https://github.com/PeterPontbriand/investment-analysis-engine/issues/152
"""

from __future__ import annotations

import ctypes
import gc
import importlib.util
import os
import re
import sqlite3
import sys
import sysconfig
import tracemalloc
from collections.abc import Callable, Generator
from pathlib import Path

import pytest

# Frames kept per allocation; the nearest frames are kept, so the deepest worker-thread stack still shows the
# peewee frame that called ``sqlite3.connect`` and, further up, the yfinance frame that asked for the cache.
_TRACEMALLOC_FRAMES = 25

# The one excused leak is yfinance's, through its peewee cache: the nearest non-standard-library frame of the
# allocation is in peewee (the frame that calls ``sqlite3.connect``), and a yfinance frame appears further up the same
# stack (``yfinance/cache.py``). Both are required. peewee alone is not enough: it is a general ORM, and a SQLite
# connection that this project or another package opens through peewee is a leak to fix, not one to excuse. The rule
# is added for a leak observed in a live run; widening it is done only for another observed leak, never in advance.
_CACHE_PACKAGE = "peewee"
_OWNER_PACKAGE = "yfinance"

_NOTICE_HEADING = "live leaks excused (SQLite connections left open by third-party caches, issue #152)"

# One line per excused leak, printed in the terminal summary so the live-check output shows each one.
_notices: list[str] = []


def _normalise(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def _is_inside(candidate: str, location: str) -> bool:
    return candidate == location or candidate.startswith(location + os.sep)


def _package_locations(name: str) -> list[str]:
    """Return where the installed package *name* lives, found at run time without importing it."""
    spec = importlib.util.find_spec(name)
    if spec is None:
        return []
    if spec.submodule_search_locations:
        return [_normalise(location) for location in spec.submodule_search_locations]
    return [_normalise(spec.origin)] if spec.origin else []


def _standard_library_locations() -> list[str]:
    """Return the standard-library folders; site-packages, which may lie below them, is not included."""
    paths = sysconfig.get_paths()
    return [_normalise(paths[key]) for key in ("stdlib", "platstdlib") if paths.get(key)]


def _site_locations() -> list[str]:
    paths = sysconfig.get_paths()
    return [_normalise(paths[key]) for key in ("purelib", "platlib") if paths.get(key)]


def _is_standard_library(filename: str) -> bool:
    if filename.startswith("<"):
        return True  # frozen and built-in modules
    candidate = _normalise(filename)
    if any(_is_inside(candidate, site) for site in _site_locations()):
        return False
    return any(_is_inside(candidate, location) for location in _standard_library_locations())


def _is_in_package(filename: str, package: str) -> bool:
    candidate = _normalise(filename)
    return any(_is_inside(candidate, location) for location in _package_locations(package))


def attribution(leaked: object) -> str | None:
    """Return the notice text when *leaked* is yfinance's leak through peewee, or ``None`` when it must not be excused.

    The allocation traceback runs oldest frame first, so the search starts from the end. Standard-library frames
    (``threading`` and the like) are skipped; the first frame beyond them must be in peewee, and a yfinance frame
    must appear further up (earlier in the traceback). A missing traceback is never excused.
    """
    traceback = tracemalloc.get_object_traceback(leaked)
    if traceback is None:
        return None
    frames = [frame.filename for frame in reversed(traceback) if not _is_standard_library(frame.filename)]
    if not frames or not _is_in_package(frames[0], _CACHE_PACKAGE):
        return None
    if any(_is_in_package(filename, _OWNER_PACKAGE) for filename in frames[1:]):
        return f"{_CACHE_PACKAGE} for {_OWNER_PACKAGE}"
    return None


# What CPython 3.14 reports for an unclosed SQLite connection that is being freed: the connection is named only in
# this message, and ``UnraisableHookArgs.object`` is ``None``. The whole message must match; nothing else is read.
_FINALIZING_MESSAGE = re.compile(
    r"Exception ignored while finalizing database connection <sqlite3\.Connection object at (0x[0-9A-Fa-f]+)>"
)


def _leaked_object(unraisable: sys.UnraisableHookArgs) -> object | None:
    """Return the object an unraisable event is about, or ``None`` when it cannot be established safely.

    Python 3.12 and 3.13 pass the object in ``unraisable.object``, and it is used whenever it is present. Python
    3.14 reports a leaked connection with ``object`` set to ``None`` and names it only by address in the message,
    so the address is turned back into the object. Dereferencing an address is safe only while the connection's own
    finalizer is reporting it: the interpreter is still inside that finalizer, which keeps the object alive until
    the hook returns. For that reason the address is trusted only from the complete message CPython writes for that
    report. A message that does not match, because CPython changed its text or the event is about something else,
    recovers nothing, so the event goes unexcused to the wrapped hook and fails the run instead of hiding a leak.
    """
    if unraisable.object is not None:
        return unraisable.object
    match = _FINALIZING_MESSAGE.fullmatch(unraisable.err_msg or "")
    if match is None:
        return None
    return ctypes.cast(int(match.group(1), 16), ctypes.py_object).value  # type: ignore[no-any-return]


def _excusing_attribution(unraisable: sys.UnraisableHookArgs) -> str | None:
    """Return the attribution for an excusable event, or ``None``.

    The recovered reference lives only inside this function, so it is gone before the hook returns.
    """
    leaked = _leaked_object(unraisable)
    try:
        if isinstance(leaked, sqlite3.Connection):
            return attribution(leaked)
        return None
    finally:
        del leaked


def _wrapping_hook(
    wrapped: Callable[[sys.UnraisableHookArgs], object],
) -> Callable[[sys.UnraisableHookArgs], object]:
    def hook(unraisable: sys.UnraisableHookArgs) -> object:
        """Excuse yfinance's SQLite leak; hand every other event, unchanged, to the wrapped hook.

        This sees leaks from every live test, not only the Yahoo check. An event is excused only for a
        ``sqlite3.Connection`` whose allocation traceback attributes it to yfinance through peewee. A connection
        with no traceback (it was allocated before tracing began) is not excused, because its allocator is unknown.
        """
        try:
            attributed = _excusing_attribution(unraisable)
        except Exception:  # noqa: BLE001 - attribution must never hide an event; fall through to the wrapped hook
            attributed = None
        if attributed is not None:
            _notices.append(f"excused a leaked sqlite3.Connection allocated by {attributed}")
            return None
        return wrapped(unraisable)

    return hook


@pytest.fixture(scope="session", autouse=True)
def _attribute_sqlite_leaks() -> Generator[None]:
    """Trace allocations and wrap the unraisable hook for the live tests, then restore both."""
    started_tracing = not tracemalloc.is_tracing() or tracemalloc.get_traceback_limit() < _TRACEMALLOC_FRAMES
    if started_tracing:
        tracemalloc.stop()
        tracemalloc.start(_TRACEMALLOC_FRAMES)
    _notices.clear()
    previous = sys.unraisablehook
    sys.unraisablehook = _wrapping_hook(previous)
    try:
        yield
        # A leaked connection can sit in a dead thread's state until a garbage collection frees it. Collect now,
        # while the hook is still installed, so an excused leak is excused and noticed here and not freed unseen
        # by the collection pytest runs at the end of the session.
        gc.collect()
    finally:
        sys.unraisablehook = previous
        if started_tracing:
            tracemalloc.stop()


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Print one line for each excused leak, so no leak is excused silently."""
    if not _notices:
        return
    terminalreporter.section(_NOTICE_HEADING)
    for notice in _notices:
        terminalreporter.write_line(notice)
