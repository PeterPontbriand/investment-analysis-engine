"""Classify a change set for CI: report whether it is documentation only.

Reads NUL-separated paths (the output of ``git diff --name-only -z``) from standard input and prints
``docs_only=true`` or ``docs_only=false``, ready to append to ``$GITHUB_OUTPUT``. A change is documentation only when
it has at least one path, every path is Markdown or lies under ``docs/``, and no path lies under
``investment_analysis_engine/``, ``schemas/`` or ``tests/``. Standard library only.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

CODE_FOLDERS = ("investment_analysis_engine/", "schemas/", "tests/")
"""Folders whose files are never documentation, even when they are Markdown."""

DOCS_FOLDER = "docs/"
MARKDOWN_SUFFIX = ".md"


def parse_paths(text: str) -> list[str]:
    """Split NUL-separated text into paths, dropping empty entries such as the one after a trailing NUL."""
    return [path for path in text.split("\0") if path]


def is_docs_only(paths: Sequence[str]) -> bool:
    """Return whether a non-empty change touches only documentation."""
    if not paths:
        return False
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized.startswith(CODE_FOLDERS):
            return False
        if not (normalized.endswith(MARKDOWN_SUFFIX) or normalized.startswith(DOCS_FOLDER)):
            return False
    return True


def main() -> int:
    """Read paths from standard input and print the classification."""
    paths = parse_paths(sys.stdin.buffer.read().decode("utf-8"))
    sys.stdout.write(f"docs_only={'true' if is_docs_only(paths) else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
