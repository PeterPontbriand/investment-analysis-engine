"""Path validation shared by settings and command-line path options."""

import sys
from pathlib import PureWindowsPath

_HOW_TO_CONVERT = "in Git Bash, 'cygpath -m <path>' prints the Windows form."


def is_windows() -> bool:
    """Return whether the process runs on Windows; tests patch this one seam to exercise the rule elsewhere."""
    return sys.platform == "win32"


def require_anchored_path(value: str, *, name: str, windows: bool) -> None:
    """Reject a path that Windows would only partly anchor.

    On Windows a path with a root but no drive (``/e/Source/x``, how Git Bash writes paths) resolves
    against the root of the current drive, and a path with a drive but no root (``E:data``) resolves
    against that drive's current folder. Both create data somewhere the user did not intend, so only
    relative paths and fully qualified paths (drive and root, or UNC) are accepted.

    Args:
        value: The raw path as configured or typed, before any resolution.
        name: The setting or option the path came from, used in the message.
        windows: Whether to apply the Windows rule. Pass ``sys.platform == "win32"``; the rule is
            built on ``PureWindowsPath`` so it can be tested on any operating system. When false,
            nothing is checked.

    Raises:
        ValueError: With a one-line explanation and, when one is evident, the path probably meant.
    """
    if not windows:
        return
    path = PureWindowsPath(value)
    if bool(path.drive) == bool(path.root):
        return
    if path.root:
        suggestion = _drive_suggestion(path)
        advice = (
            f"Use a full path such as '{suggestion}'"
            if suggestion is not None
            else "Use a full path that starts with a drive letter"
        )
        raise ValueError(
            f"{name} path '{value}' has a root but no drive letter, so Windows would place it under "
            f"the current drive's root. {advice} or a path relative to the project folder; {_HOW_TO_CONVERT}"
        )
    rest = "/".join(path.parts[1:])
    raise ValueError(
        f"{name} path '{value}' has a drive letter but no root, so Windows would resolve it against "
        f"that drive's current folder. Use a full path such as '{path.drive.upper()}/{rest}' or a path relative "
        f"to the project folder; {_HOW_TO_CONVERT}"
    )


def _drive_suggestion(path: PureWindowsPath) -> str | None:
    """Return ``E:/rest`` for ``/e/rest``, or None when the first segment is not one ASCII letter."""
    segments = path.parts[1:]
    if not segments:
        return None
    first = segments[0]
    if len(first) != 1 or not first.isascii() or not first.isalpha():
        return None
    return f"{first.upper()}:/{'/'.join(segments[1:])}"
