"""Prove the live-test selection hook deselects marked tests by default and selects only them under ``--live``.

Each case runs a tiny inner test session that loads the real hook and guard fixtures, so selection behaves
exactly as it does for the project's own suite, including under ``-o addopts=`` as the managed wrappers run it.
The synthetic marked test makes no network call.
"""

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.as_posix()
_INNER_CONFTEST = """
from tests._live_selection import pytest_addoption, pytest_collection_modifyitems, pytest_configure  # noqa: F401
from tests._network_guard import block_external_sockets, block_live_yahoo  # noqa: F401
"""
_INNER_TESTS = """
import socket

import pytest

@pytest.mark.live_network
def test_marked() -> None:
    assert socket.socket.connect is not None

def test_unmarked() -> None:
    assert True
"""


def _session(pytester: pytest.Pytester) -> None:
    pytester.makeini("[pytest]\nasyncio_default_fixture_loop_scope = function\n")
    pytester.makeconftest(_INNER_CONFTEST)
    pytester.makepyfile(_INNER_TESTS)


def test_default_run_deselects_the_marked_test(pytester: pytest.Pytester) -> None:
    _session(pytester)
    result = pytester.runpytest("-p", "no:cacheprovider", "-v")
    result.assert_outcomes(passed=1, deselected=1)
    result.stdout.fnmatch_lines(["*test_unmarked PASSED*"])
    assert "test_marked" not in "\n".join(line for line in result.outlines if "PASSED" in line)


def test_live_option_selects_only_the_marked_test(pytester: pytest.Pytester) -> None:
    _session(pytester)
    result = pytester.runpytest("-p", "no:cacheprovider", "-v", "--live")
    result.assert_outcomes(passed=1, deselected=1)
    result.stdout.fnmatch_lines(["*test_marked PASSED*"])


def test_default_run_deselects_the_marked_test_when_addopts_is_overridden(pytester: pytest.Pytester) -> None:
    _session(pytester)
    result = pytester.runpytest("-o", "addopts=", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=1, deselected=1)


def test_marker_is_registered(pytester: pytest.Pytester) -> None:
    _session(pytester)
    result = pytester.runpytest("--markers")
    result.stdout.fnmatch_lines(["*live_network*"])


def test_marked_test_is_exempt_from_the_guards_and_an_unmarked_one_is_not(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYTHONPATH", _REPOSITORY_ROOT)
    pytester.makeini("[pytest]\nasyncio_default_fixture_loop_scope = function\n")
    pytester.makeconftest(_INNER_CONFTEST)
    pytester.makepyfile(
        """
        import socket

        import pytest

        def _guard_installed() -> bool:
            return socket.socket.connect.__qualname__.endswith("guarded")

        @pytest.mark.live_network
        def test_marked() -> None:
            assert not _guard_installed()

        def test_unmarked() -> None:
            assert _guard_installed()
        """
    )
    for live in (False, True):
        # A subprocess keeps the outer session's own guards out of the inner session.
        result = pytester.runpytest_subprocess("-p", "no:cacheprovider", *(["--live"] if live else []))
        result.assert_outcomes(passed=1, deselected=1)
