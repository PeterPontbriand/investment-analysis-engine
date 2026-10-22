"""Prove the ``WinError 10055`` hook attaches one snapshot to the right report and never changes an outcome.

Each hook case runs a tiny inner pytest session that loads the real hook with a fake collector, so the snapshot
reaches the failure output exactly as it does for the project's own suite. The real collector runs only on Windows.
"""

import sys

import pytest

pytest_plugins = ["pytester"]

_INNER_CONFTEST = """
import pytest

from tests import _socket_snapshot
from tests._socket_snapshot import pytest_runtest_makereport  # noqa: F401

CALLS = []

def collect():
    CALLS.append(1)
    if COLLECTOR_FAILS:
        raise RuntimeError("powershell is not available")
    return "tcp connections by state: 3 total; Established=3"

def pytest_configure(config):
    config.stash[_socket_snapshot.SNAPSHOT_COLLECTOR] = collect
"""
_INNER_TESTS = """
import pytest

def exhausted(chained=False):
    error = OSError("An operation on a socket could not be performed because the system lacked sufficient buffer space")
    error.winerror = 10055
    if not chained:
        return error
    wrapper = RuntimeError("event loop could not be created")
    wrapper.__cause__ = error
    return wrapper

@pytest.fixture
def broken_setup():
    raise exhausted()

@pytest.fixture
def broken_teardown():
    yield
    raise exhausted()

def test_direct():
    raise exhausted()

def test_chained():
    raise exhausted(chained=True)

def test_setup(broken_setup):
    pass

def test_teardown(broken_teardown):
    pass

def test_other_os_error():
    error = OSError("another failure")
    error.winerror = 10048
    raise error

def test_plain_assertion():
    assert False, "plain"

def test_passes():
    pass
"""
_SNAPSHOT_LINE = "tcp connections by state: 3 total; Established=3"


def _run(pytester: pytest.Pytester, expression: str, *, collector_fails: bool = False) -> pytest.RunResult:
    pytester.makeini("[pytest]\nasyncio_default_fixture_loop_scope = function\n")
    pytester.makeconftest(f"COLLECTOR_FAILS = {collector_fails!r}\n{_INNER_CONFTEST}")
    pytester.makepyfile(_INNER_TESTS)
    return pytester.runpytest("-p", "no:cacheprovider", "-k", expression)


def _snapshot_sections(result: pytest.RunResult) -> int:
    return sum("socket snapshot" in line and line.startswith("-") for line in result.outlines)


def test_a_failure_with_winerror_10055_gets_one_snapshot_and_keeps_its_outcome(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "test_direct")
    result.assert_outcomes(failed=1)
    assert _snapshot_sections(result) == 1
    result.stdout.fnmatch_lines([f"*{_SNAPSHOT_LINE}*"])


def test_winerror_10055_anywhere_in_the_cause_chain_counts(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "test_chained")
    result.assert_outcomes(failed=1)
    assert _snapshot_sections(result) == 1


def test_a_setup_failure_gets_a_snapshot_and_stays_an_error(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "test_setup")
    result.assert_outcomes(errors=1)
    assert _snapshot_sections(result) == 1


def test_a_teardown_failure_gets_a_snapshot_and_keeps_the_passing_call(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "test_teardown")
    result.assert_outcomes(passed=1, errors=1)
    assert _snapshot_sections(result) == 1


def test_a_second_failure_in_the_same_session_gets_no_snapshot(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "test_direct or test_chained or test_setup")
    result.assert_outcomes(failed=2, errors=1)
    assert _snapshot_sections(result) == 1
    assert result.stdout.str().count(_SNAPSHOT_LINE) == 1


@pytest.mark.parametrize("expression", ["test_other_os_error", "test_plain_assertion"])
def test_an_unrelated_failure_gets_no_snapshot(pytester: pytest.Pytester, expression: str) -> None:
    result = _run(pytester, expression)
    result.assert_outcomes(failed=1)
    assert _snapshot_sections(result) == 0
    assert _SNAPSHOT_LINE not in result.stdout.str()


def test_an_unrelated_failure_does_not_use_up_the_session_snapshot(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "test_plain_assertion or test_direct")
    result.assert_outcomes(failed=2)
    assert _snapshot_sections(result) == 1


def test_a_passing_test_gets_no_snapshot(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "test_passes")
    result.assert_outcomes(passed=1)
    assert _snapshot_sections(result) == 0


def test_a_failing_collector_records_why_and_keeps_the_outcome(pytester: pytest.Pytester) -> None:
    result = _run(pytester, "test_direct", collector_fails=True)
    result.assert_outcomes(failed=1)
    assert _snapshot_sections(result) == 1
    result.stdout.fnmatch_lines(["*snapshot not collected: RuntimeError: powershell is not available*"])


def test_the_hook_does_nothing_without_a_collector_off_windows(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests import _socket_snapshot  # noqa: PLC0415

    monkeypatch.setattr(_socket_snapshot, "_platform_is_windows", lambda: False)
    pytester.makeini("[pytest]\nasyncio_default_fixture_loop_scope = function\n")
    pytester.makeconftest("from tests._socket_snapshot import pytest_runtest_makereport  # noqa: F401\n")
    pytester.makepyfile(_INNER_TESTS)
    result = pytester.runpytest("-p", "no:cacheprovider", "-k", "test_direct")
    result.assert_outcomes(failed=1)
    assert _snapshot_sections(result) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="the real collector uses Windows PowerShell")
def test_the_real_collector_returns_every_section() -> None:
    from tests._socket_snapshot import collect_socket_snapshot  # noqa: PLC0415

    snapshot = collect_socket_snapshot()
    labels = [line.split(":", 1)[0] for line in snapshot.splitlines()]
    assert labels == [
        "tcp connections by state",
        "top tcp owners",
        "dynamic tcp port range",
        "non-paged pool bytes",
        "available memory bytes",
        "python processes",
        "python handles total",
    ]
    assert not any("unavailable" in line for line in snapshot.splitlines()), snapshot
