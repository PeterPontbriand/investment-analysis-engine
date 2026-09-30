"""Tests for the Windows path anchoring guard; they run on every OS through the ``windows`` flag."""

import pytest

from src.utils.paths import require_anchored_path

_ACCEPTED = [
    "data/x.sqlite3",
    "x.sqlite3",
    ".tmp/probe/x.sqlite3",
    "..\\shared\\x.sqlite3",
    "E:/Source/x.sqlite3",
    "E:\\Source\\x.sqlite3",
    "e:/source/x.sqlite3",
    "\\\\server\\share\\x.sqlite3",
    "//server/share/x.sqlite3",
]

_ROOT_WITHOUT_DRIVE = ["/e/Source/x.sqlite3", "\\e\\Source\\x.sqlite3", "/data/x.sqlite3", "/tmp/x"]

_DRIVE_WITHOUT_ROOT = ["E:data", "E:data/x.sqlite3", "e:x.sqlite3"]


@pytest.mark.parametrize("value", _ACCEPTED)
def test_relative_and_fully_qualified_paths_are_accepted_on_windows(value: str) -> None:
    require_anchored_path(value, name="database_url", windows=True)


@pytest.mark.parametrize("value", [*_ACCEPTED, *_ROOT_WITHOUT_DRIVE, *_DRIVE_WITHOUT_ROOT])
def test_every_path_is_accepted_when_not_on_windows(value: str) -> None:
    require_anchored_path(value, name="database_url", windows=False)


@pytest.mark.parametrize("value", _ROOT_WITHOUT_DRIVE)
def test_a_root_without_a_drive_is_rejected_on_windows(value: str) -> None:
    with pytest.raises(ValueError, match="has a root but no drive letter") as error:
        require_anchored_path(value, name="log_dir", windows=True)
    message = str(error.value)
    assert message.startswith(f"log_dir path '{value}'")
    assert "current drive's root" in message
    assert "path relative to the project folder" in message
    assert "cygpath -m" in message
    assert "\n" not in message


@pytest.mark.parametrize("value", _DRIVE_WITHOUT_ROOT)
def test_a_drive_without_a_root_is_rejected_on_windows(value: str) -> None:
    with pytest.raises(ValueError, match="has a drive letter but no root") as error:
        require_anchored_path(value, name="data_dir", windows=True)
    message = str(error.value)
    assert message.startswith(f"data_dir path '{value}'")
    assert "that drive's current folder" in message
    assert "\n" not in message


@pytest.mark.parametrize(
    ("value", "suggestion"),
    [
        ("/e/Source/x.sqlite3", "E:/Source/x.sqlite3"),
        ("\\c\\Users\\me\\x", "C:/Users/me/x"),
        ("/e", "E:/"),
        ("E:data", "E:/data"),
        ("e:data/x.sqlite3", "E:/data/x.sqlite3"),
    ],
)
def test_the_message_suggests_the_path_the_user_probably_meant(value: str, suggestion: str) -> None:
    with pytest.raises(ValueError, match="Use a full path such as") as error:
        require_anchored_path(value, name="database_url", windows=True)
    assert f"Use a full path such as '{suggestion}'" in str(error.value)


@pytest.mark.parametrize("value", ["/data/x.sqlite3", "/tmp/x", "/ab/x"])
def test_no_drive_suggestion_is_made_when_the_first_segment_is_not_a_single_letter(value: str) -> None:
    with pytest.raises(ValueError, match="no drive letter|drive letter") as error:
        require_anchored_path(value, name="database_url", windows=True)
    assert "such as" not in str(error.value)
    assert "Use a full path that starts with a drive letter" in str(error.value)
