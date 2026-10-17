"""Prove the live-check leak attribution excuses yfinance's SQLite leak and nothing else.

Each case runs an inner pytest session in a subprocess (so tracing and the unraisable hook stay out of this
session) under a copy of the real ``tests/live/conftest.py``, with the same warning filters the project uses.
The inner tests allocate a ``sqlite3.Connection`` from code whose recorded file lies where the case needs it, then
leave the connection in a worker thread's thread-local state, which is how peewee leaves it. Python 3.13 and later
warn when such a connection is freed (3.14 with no object, only the address in the message); 3.12 does not, so
there the inner test delivers the same event, carrying the object, to ``sys.unraisablehook`` itself. The cases
that deliver an event by hand with ``by_address`` exercise the address path on every Python version.
The yfinance and peewee locations are read from the installed package at run time.
"""

from __future__ import annotations

import pytest

from scripts.repository_root import REPOSITORY_ROOT

pytest_plugins = ["pytester"]

_LIVE_CONFTEST = REPOSITORY_ROOT / "tests" / "live" / "conftest.py"
_INI = """
[pytest]
filterwarnings =
    error::ResourceWarning
    error::pytest.PytestUnraisableExceptionWarning
asyncio_default_fixture_loop_scope = function
"""
_HELPERS = '''
import importlib.util
import sqlite3
import sys
import threading
import types
from pathlib import Path

OLD_PYTHON = sys.version_info < (3, 13)
_state = threading.local()


def location_of(package):
    spec = importlib.util.find_spec(package)
    if spec.submodule_search_locations:
        return Path(list(spec.submodule_search_locations)[0])
    return Path(spec.origin)


def yfinance_file():
    return location_of("yfinance") / "stand_in.py"


def allocator(*recorded_files):
    """Return a function that opens a connection through nested calls, one per file, outermost file first.

    Each function's code is recorded as living in its file, so the allocation stack that tracemalloc keeps shows
    those files from the outermost caller to the innermost, which calls ``sqlite3.connect``.
    """
    namespace = {"sqlite3": sqlite3}
    for index, recorded in enumerate(recorded_files):
        last = index == len(recorded_files) - 1
        body = "sqlite3.connect(':memory:')" if last else f"f{index + 1}()"
        exec(compile(f"def f{index}():" + chr(10) + f"    return {body}" + chr(10), str(recorded), "exec"), namespace)
    return namespace["f0"]


def yfinance_through_peewee():
    """Stand-in for yfinance's cache: a yfinance frame above a peewee frame that opens the connection."""
    return allocator(yfinance_file(), location_of("peewee"))


def finalizing_message(leaked):
    return f"Exception ignored while finalizing database connection <sqlite3.Connection object at {id(leaked):#x}>"


def deliver(leaked, *, by_address=False, err_msg=None):
    """Deliver the event CPython raises for an unclosed connection (3.12 raises none).

    By default the event carries the object, as 3.12 and 3.13 report it. With ``by_address`` it carries ``None``
    and names the connection only in the message, as 3.14 reports it. ``err_msg`` replaces the message.
    """
    event = types.SimpleNamespace(
        exc_type=ResourceWarning,
        exc_value=ResourceWarning("unclosed database"),
        exc_traceback=None,
        err_msg=err_msg if err_msg is not None else finalizing_message(leaked),
        object=None if by_address else leaked,
    )
    sys.unraisablehook(event)


def leak_from_worker_thread(make):
    """Leave the object in a worker thread's thread-local state; it is freed when that thread ends."""
    captured = []

    def worker():
        _state.leaked = make()
        if OLD_PYTHON:
            captured.append(_state.leaked)

    thread = threading.Thread(target=worker, name="provider-check", daemon=True)
    thread.start()
    thread.join()
    for leaked in captured:
        deliver(leaked)
'''


def _run(pytester: pytest.Pytester, tests: str) -> pytest.RunResult:
    pytester.makeini(_INI)
    pytester.makeconftest(_LIVE_CONFTEST.read_text(encoding="utf-8"))
    pytester.makepyfile(helpers=_HELPERS)
    pytester.makepyfile(tests)
    return pytester.runpytest_subprocess("-p", "no:cacheprovider", "-s")


def _assert_run_fails_unexcused(result: pytest.RunResult) -> None:
    """The inner session failed (as a test failure or, when the leak is freed at teardown, an error); no notice."""
    assert result.ret != 0
    assert "excused a leaked" not in result.stdout.str()


def test_a_connection_allocated_by_yfinance_through_peewee_is_excused_with_a_notice(
    pytester: pytest.Pytester,
) -> None:
    """Stands for yfinance's cache: a yfinance frame above the peewee frame that opens it, leaked from a worker."""
    result = _run(
        pytester,
        """
        from helpers import leak_from_worker_thread, yfinance_through_peewee

        def test_leak() -> None:
            leak_from_worker_thread(yfinance_through_peewee())
        """,
    )
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*excused a leaked sqlite3.Connection allocated by peewee for yfinance*"])


def test_a_connection_allocated_through_peewee_without_yfinance_still_fails(pytester: pytest.Pytester) -> None:
    """Stands for a peewee-style allocation by this project's own code: peewee alone is not yfinance's leak."""
    result = _run(
        pytester,
        """
        from helpers import allocator, leak_from_worker_thread, location_of

        def test_leak() -> None:
            leak_from_worker_thread(allocator(__file__, location_of("peewee")))
        """,
    )
    _assert_run_fails_unexcused(result)


def test_a_connection_allocated_directly_by_yfinance_still_fails(pytester: pytest.Pytester) -> None:
    """Stands for a yfinance frame that is nearest the allocation: only the peewee cache path is excused."""
    result = _run(
        pytester,
        """
        from helpers import allocator, leak_from_worker_thread, yfinance_file

        def test_leak() -> None:
            leak_from_worker_thread(allocator(yfinance_file()))
        """,
    )
    _assert_run_fails_unexcused(result)


def test_a_connection_allocated_by_project_code_still_fails(pytester: pytest.Pytester) -> None:
    """Stands for a leak in this project's own code, which must keep failing."""
    result = _run(
        pytester,
        """
        from helpers import allocator, leak_from_worker_thread

        def test_leak() -> None:
            leak_from_worker_thread(allocator(__file__))
        """,
    )
    _assert_run_fails_unexcused(result)


def test_a_connection_with_no_allocation_traceback_still_fails(pytester: pytest.Pytester) -> None:
    """Stands for a connection allocated before tracing began, whose allocator cannot be known."""
    result = _run(
        pytester,
        """
        import sqlite3

        from helpers import OLD_PYTHON, deliver

        EARLY = [sqlite3.connect(":memory:")]

        def test_leak() -> None:
            leaked = EARLY.pop()
            if OLD_PYTHON:
                deliver(leaked)
            del leaked
        """,
    )
    _assert_run_fails_unexcused(result)


def test_a_leaked_object_of_another_type_still_fails(pytester: pytest.Pytester) -> None:
    """Stands for any other unraisable event, even one allocated by yfinance through peewee."""
    result = _run(
        pytester,
        """
        import threading

        from helpers import yfinance_file

        class Leaky:
            def __del__(self) -> None:
                raise RuntimeError("finalizer failed")

        def test_leak() -> None:
            recorded = yfinance_file()
            code = compile("def make(cls):\\n    return cls()\\n", str(recorded), "exec")
            namespace = {}
            exec(code, namespace)
            state = threading.local()
            thread = threading.Thread(target=lambda: setattr(state, "leaked", namespace["make"](Leaky)))
            thread.start()
            thread.join()
        """,
    )
    _assert_run_fails_unexcused(result)


def test_a_yfinance_connection_named_only_by_its_address_is_excused(pytester: pytest.Pytester) -> None:
    """Stands for the Python 3.14 report: no object, the connection named by address in the message."""
    result = _run(
        pytester,
        """
        from helpers import deliver, yfinance_through_peewee

        def test_event() -> None:
            leaked = yfinance_through_peewee()()
            deliver(leaked, by_address=True)
            leaked.close()  # only the delivered event is under test; the real object must not report one too
        """,
    )
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*excused a leaked sqlite3.Connection allocated by peewee for yfinance*"])


def test_a_message_that_does_not_match_the_report_is_not_excused(pytester: pytest.Pytester) -> None:
    """Stands for CPython rewording its message: the address cannot be trusted, so the event must fail."""
    result = _run(
        pytester,
        """
        from helpers import deliver, finalizing_message, yfinance_through_peewee

        def test_event() -> None:
            leaked = yfinance_through_peewee()()
            deliver(leaked, by_address=True, err_msg=finalizing_message(leaked).replace("finalizing", "closing"))
            leaked.close()  # only the delivered event is under test; the real object must not report one too
        """,
    )
    _assert_run_fails_unexcused(result)


def test_a_matching_message_for_a_project_connection_is_not_excused(pytester: pytest.Pytester) -> None:
    """Stands for a project-side leak reported the Python 3.14 way: recovered, attributed, and still failing."""
    result = _run(
        pytester,
        """
        from helpers import allocator, deliver

        def test_event() -> None:
            leaked = allocator(__file__)()
            deliver(leaked, by_address=True)
            leaked.close()  # only the delivered event is under test; the real object must not report one too
        """,
    )
    _assert_run_fails_unexcused(result)


def test_a_matching_message_for_an_object_that_is_not_a_connection_is_not_excused(pytester: pytest.Pytester) -> None:
    """Stands for an address that resolves to something else: it is not a connection, so it is not excused."""
    result = _run(
        pytester,
        """
        from helpers import deliver

        def test_event() -> None:
            deliver(["not a connection"], by_address=True)
        """,
    )
    _assert_run_fails_unexcused(result)
