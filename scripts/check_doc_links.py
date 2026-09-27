"""Repo-wide Markdown local-link and heading-anchor checker.

Walks every git-tracked ``.md`` file, resolves every local ``[text](path)``,
``[text](#anchor)``, and ``[text](path#anchor)`` link, and reports every break
in one run. External links (anything with a URL scheme, e.g. ``https://`` or
``mailto:``) are skipped entirely -- this script makes no network access.
Fenced code blocks (``` or ~~~) are skipped, since a link shown as an example
inside one is not a real link.

Anchor slugs are generated the way GitHub renders heading anchors: lowercase,
a fixed set of ASCII punctuation stripped, each remaining whitespace character
replaced with its own hyphen (runs are not collapsed, matching GitHub's actual
behavior for headings such as ``FCF & Earnings Growth``, which produces a
double hyphen), and a ``-1``, ``-2``, ... suffix appended to each repeated
heading in document order. Markdown emphasis (``**bold**``, ``` `code` ```)
is stripped before slugifying, matching the rendered text a heading actually
produces; single ``*`` or ``_`` emphasis is deliberately left untouched, since
distinguishing it from a literal asterisk or underscore requires full
CommonMark flanking-delimiter rules that this small checker does not
implement -- no heading in this repository currently depends on that
distinction, and inline code spans already cover the common case.

Only inline links (``[text](target)``) are recognized; reference-style links
(``[text][ref]``) are not used anywhere in this repository's Markdown and are
out of scope.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^(```+|~~~+)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_MARKDOWN_LINK_IN_TEXT_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_EMPHASIS_MARKUP_RE = re.compile(r"\*\*|__|`")
_SLUG_PUNCTUATION_RE = re.compile(r"""[!"#$%&'()*+,./:;<=>?@\[\]\\^{|}~ -⁯⸀-⹿]""")


@dataclass(frozen=True)
class BrokenLink:
    """One local link or anchor that does not resolve."""

    source_file: Path
    line_number: int
    link_text: str
    target: str
    reason: str

    def __str__(self) -> str:
        """Render as ``path:line: [text](target) -- reason``."""
        return f"{self.source_file}:{self.line_number}: [{self.link_text}]({self.target}) -- {self.reason}"


def strip_markdown_markup(text: str) -> str:
    """Reduce heading source text toward its rendered form for slugifying.

    Replaces an inline link with its link text, and drops emphasis/code
    delimiters, since none of those characters survive into GitHub's
    rendered heading text.
    """
    text = _MARKDOWN_LINK_IN_TEXT_RE.sub(r"\1", text)
    return _EMPHASIS_MARKUP_RE.sub("", text)


def slugify(heading_text: str) -> str:
    """Return the GitHub-style anchor slug for one heading's raw text.

    Does not apply the duplicate-heading ``-1``/``-2`` suffix; see
    :func:`file_heading_slugs` for that.
    """
    text = strip_markdown_markup(heading_text).strip().lower()
    text = _SLUG_PUNCTUATION_RE.sub("", text)
    return re.sub(r"\s", "-", text)


def iter_non_fenced_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Return ``(1-indexed line number, line)`` pairs, skipping fenced code blocks."""
    result: list[tuple[int, str]] = []
    in_fence = False
    fence_marker = ""
    for index, line in enumerate(lines, start=1):
        stripped = line.rstrip("\n")
        fence_match = _FENCE_RE.match(stripped.strip())
        if fence_match:
            if not in_fence:
                in_fence = True
                fence_marker = fence_match.group(1)[0] * 3
            elif stripped.strip().startswith(fence_marker):
                in_fence = False
            continue
        if in_fence:
            continue
        result.append((index, stripped))
    return result


def file_heading_slugs(lines: list[str]) -> set[str]:
    """Return every heading anchor slug a Markdown file's lines produce.

    Applies GitHub's duplicate-heading suffixing: the first heading that
    slugifies to ``x`` keeps ``x``; the second becomes ``x-1``; the third
    ``x-2``; and so on, in document order, skipping fenced code blocks.
    """
    slugs: set[str] = set()
    counts: dict[str, int] = {}
    for _line_number, line in iter_non_fenced_lines(lines):
        heading_match = _ATX_HEADING_RE.match(line)
        if heading_match is None:
            continue
        base_slug = slugify(heading_match.group(2))
        if not base_slug:
            continue
        count = counts.get(base_slug, 0)
        counts[base_slug] = count + 1
        slugs.add(base_slug if count == 0 else f"{base_slug}-{count}")
    return slugs


def _is_external(target: str) -> bool:
    return bool(_SCHEME_RE.match(target)) or target.startswith("//")


def find_broken_links_in_file(
    source_file: Path,
    lines: list[str],
    *,
    repo_root: Path,
    heading_slug_cache: dict[Path, set[str]],
) -> list[BrokenLink]:
    """Return every broken local link/anchor found in one file's lines.

    A same-file ``#anchor`` link is checked against ``lines`` directly rather
    than by re-reading ``source_file`` from disk, since the caller may be
    checking content that has not been written to disk yet (as the tests do)
    and re-reading the file currently being processed is redundant besides.
    """
    broken: list[BrokenLink] = []
    for line_number, line in iter_non_fenced_lines(lines):
        for match in _LINK_RE.finditer(line):
            link_text, target = match.group(1), match.group(2).strip()
            if not target or _is_external(target):
                continue
            path_part, _, anchor = target.partition("#")
            target_file: Path | None = None
            if path_part:
                resolved = (source_file.parent / path_part).resolve()
                if not resolved.exists():
                    broken.append(
                        BrokenLink(
                            source_file, line_number, link_text, target, f"target path does not exist: {path_part}"
                        )
                    )
                    continue
                target_file = resolved
            if not anchor:
                continue
            if target_file is not None and target_file.is_dir():
                broken.append(
                    BrokenLink(source_file, line_number, link_text, target, "anchor given for a directory target")
                )
                continue
            if target_file is not None and target_file.suffix.lower() != ".md":
                continue  # anchors into non-Markdown targets (e.g. line links) are out of scope
            if target_file is None:
                target_slugs = file_heading_slugs(lines)
                display_target = "this file"
            else:
                if target_file not in heading_slug_cache:
                    target_lines = target_file.read_text(encoding="utf-8").splitlines(keepends=True)
                    heading_slug_cache[target_file] = file_heading_slugs(target_lines)
                target_slugs = heading_slug_cache[target_file]
                display_target = str(target_file.relative_to(repo_root))
            if anchor not in target_slugs:
                broken.append(
                    BrokenLink(
                        source_file,
                        line_number,
                        link_text,
                        target,
                        f"no heading produces anchor #{anchor} in {display_target}",
                    )
                )
    return broken


def list_tracked_markdown_files(repo_root: Path) -> list[Path]:
    """Return every git-tracked ``.md`` file's absolute path."""
    output = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=repo_root,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [repo_root / line for line in output.splitlines() if line]


def check_repository(repo_root: Path) -> list[BrokenLink]:
    """Check every tracked Markdown file in ``repo_root`` and return all breaks found."""
    heading_slug_cache: dict[Path, set[str]] = {}
    broken: list[BrokenLink] = []
    for markdown_file in list_tracked_markdown_files(repo_root):
        lines = markdown_file.read_text(encoding="utf-8").splitlines(keepends=True)
        broken.extend(
            find_broken_links_in_file(markdown_file, lines, repo_root=repo_root, heading_slug_cache=heading_slug_cache)
        )
    return broken


def main() -> int:
    """Check the repository this script lives in; print every break; return the process exit code."""
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True, text=True
        ).stdout.strip()
    )
    broken_links = check_repository(repo_root)
    if not broken_links:
        print("check_doc_links: no broken local links or anchors found.")
        return 0
    for broken in broken_links:
        print(broken)
    print(f"check_doc_links: {len(broken_links)} broken local link(s)/anchor(s) found.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
