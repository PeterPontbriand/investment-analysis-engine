"""The scenario's path mask is covered for every spelling of one directory, on any platform.

The commands print the database path they resolved. On Windows a temporary directory is created under an 8.3 short
name and resolves to the long one; on macOS it is under ``/var``, a link to ``/private/var``. A mask built from the
unresolved spelling then misses the printed one (or leaves ``/private`` behind), which is what failed in CI. The
scenario resolves its root once, so these tests give the mask two spellings of one directory and require the printed one
to be masked.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests._workspace_command_output import _mask, scenario_root


def _dotdot_spelling(real: Path) -> Path:
    (real / "elsewhere").mkdir()
    return real / "elsewhere" / ".."


def _symlink_spelling(real: Path) -> Path:
    if sys.platform == "win32":
        pytest.skip("creating a symbolic link needs a privilege on Windows")
    link = real.parent / "link"
    link.symlink_to(real, target_is_directory=True)
    return link


def _short_name_spelling(real: Path) -> Path:
    if sys.platform != "win32":
        pytest.skip("8.3 short names exist only on Windows")
    import ctypes  # noqa: PLC0415 - Windows only

    buffer = ctypes.create_unicode_buffer(32768)
    length = getattr(ctypes, "windll").kernel32.GetShortPathNameW(str(real), buffer, len(buffer))  # noqa: B009
    if not length or Path(buffer.value).name.lower() == real.name.lower():
        pytest.skip("this volume does not create 8.3 short names")
    return Path(buffer.value)


_SPELLINGS: dict[str, Callable[[Path], Path]] = {
    "dotdot": _dotdot_spelling,
    "symlink": _symlink_spelling,
    "short-name": _short_name_spelling,
}


@pytest.fixture
def real_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "a_directory_with_a_long_name"
    directory.mkdir()
    return directory


@pytest.mark.parametrize("spelling", list(_SPELLINGS))
def test_a_printed_resolved_path_is_masked_whichever_way_the_root_was_spelled(
    real_directory: Path, spelling: str
) -> None:
    other = _SPELLINGS[spelling](real_directory)
    printed = os.path.realpath(other / "workspace.sqlite3")
    assert printed.lower() == str(real_directory.resolve() / "workspace.sqlite3").lower()

    assert _mask(f'Database: "{printed}"', [scenario_root(other)]) == 'Database: "<database>"'


@pytest.mark.parametrize("spelling", list(_SPELLINGS))
def test_masking_the_unresolved_spelling_alone_misses_the_printed_path(real_directory: Path, spelling: str) -> None:
    """Documents the cause: without resolving first, the printed form survives the mask."""
    other = _SPELLINGS[spelling](real_directory)
    printed = os.path.realpath(other / "workspace.sqlite3")
    if str(other).lower() in printed.lower():
        pytest.skip("the spelling is the resolved path, so there is nothing to miss")

    assert "<database>" not in _mask(f'Database: "{printed}"', [other])


def test_the_scenario_root_is_the_resolved_directory(real_directory: Path) -> None:
    assert scenario_root(real_directory / "x" / "..") == real_directory.resolve()
