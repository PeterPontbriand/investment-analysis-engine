"""Repo-wide Markdown local-link and heading-anchor checker.

Walks every ``.md`` file that git tracks or that is untracked and not ignored, resolves every local ``[text](path)``,
``[text](#anchor)``, and ``[text](path#anchor)`` link, and reports every break
in one run. External links (anything with a URL scheme, e.g. ``https://`` or
``mailto:``) are skipped entirely -- this script makes no network access.
Fenced code blocks (``` or ~~~) and inline code spans are skipped, since a link
shown as an example inside code is not a real link.

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

Separately, a fenced block whose language is ``mermaid`` is reported: this
repository's documentation draws diagrams as plain text blocks or tables, never
as Mermaid.

An ``<a id="x"></a>`` line is also an anchor: a link to ``#x`` resolves when such a line exists in the target file.
A link into either glossary (``GLOSSARY_PATHS``) must target such an id. A link to a glossary heading slug, which
changes when a heading is reworded, is reported even though a heading produces it.

Finally, a line inside a fenced code block of ``README.md`` or a Markdown file below ``docs/user/`` whose first word is
``ian`` is reported: every command shown to a user starts with ``uv run``, because a bare ``ian`` is not recognized
outside the installation's own Python environment.

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

GLOSSARY_PATHS = ("docs/user/GLOSSARY.md", "docs/project/CONTRIBUTOR_GLOSSARY.md")
"""The two glossaries, as repository-relative paths; a link into either must target an entry's id."""

ANCHOR_ID_RE = re.compile(r'^<a id="([^"]+)"></a>$')
"""An id line: ``<a id="..."></a>`` on a line of its own, once stripped."""

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^(```+|~~~+)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
_INLINE_CODE_SPAN_RE = re.compile(r"(?<!`)(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)")
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


USER_DOCUMENT_PREFIX = "docs/user/"
"""Repository-relative folder whose Markdown files are user documentation."""

USER_README = "README.md"
"""The repository README, which is user-facing and so held to the same command rule as the user documentation."""

_BARE_IAN_COMMAND_RE = re.compile(r"^\s*ian(\s|$)")


@dataclass(frozen=True)
class BareIanCommand:
    """One line in a fenced code block that starts with ``ian`` and not ``uv run ian``."""

    source_file: Path
    line_number: int

    def __str__(self) -> str:
        """Render as ``path:line: bare ian command -- ...``."""
        return f"{self.source_file}:{self.line_number}: bare ian command -- use `uv run ian` instead of `ian`"


def find_bare_ian_commands_in_file(source_file: Path, lines: list[str]) -> list[BareIanCommand]:
    """Return every line inside a fenced code block whose first word is ``ian``."""
    found: list[BareIanCommand] = []
    in_fence = False
    fence_marker = ""
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        fence_match = _FENCE_RE.match(stripped)
        if fence_match is not None:
            if not in_fence:
                in_fence = True
                fence_marker = fence_match.group(1)[0] * 3
            elif stripped.startswith(fence_marker):
                in_fence = False
            continue
        if in_fence and _BARE_IAN_COMMAND_RE.match(line):
            found.append(BareIanCommand(source_file, index))
    return found


@dataclass(frozen=True)
class MermaidBlock:
    """One fenced block whose language is ``mermaid``."""

    source_file: Path
    line_number: int

    def __str__(self) -> str:
        """Render as ``path:line: mermaid block -- ...``."""
        return (
            f"{self.source_file}:{self.line_number}: mermaid block -- "
            "draw the diagram as a plain text block or a table instead"
        )


def find_mermaid_blocks_in_file(source_file: Path, lines: list[str]) -> list[MermaidBlock]:
    """Return every opening fence in one file's lines whose language is ``mermaid``."""
    found: list[MermaidBlock] = []
    in_fence = False
    fence_marker = ""
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        fence_match = _FENCE_RE.match(stripped)
        if fence_match is None:
            continue
        if in_fence:
            if stripped.startswith(fence_marker):
                in_fence = False
            continue
        in_fence = True
        fence_marker = fence_match.group(1)[0] * 3
        info = stripped[len(fence_match.group(1)) :].strip().split(maxsplit=1)
        if info and info[0].lower() == "mermaid":
            found.append(MermaidBlock(source_file, index))
    return found


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


@dataclass(frozen=True)
class FileAnchors:
    """The anchors one Markdown file offers: heading slugs and ``<a id>`` ids."""

    slugs: frozenset[str]
    ids: frozenset[str]


def file_anchor_ids(lines: list[str]) -> set[str]:
    """Return every id a file's ``<a id="x"></a>`` lines give, skipping fenced code blocks."""
    ids: set[str] = set()
    for _line_number, line in iter_non_fenced_lines(lines):
        match = ANCHOR_ID_RE.match(line.strip())
        if match:
            ids.add(match.group(1))
    return ids


def file_anchors(lines: list[str]) -> FileAnchors:
    """Return the heading slugs and the ids of one file's lines."""
    return FileAnchors(frozenset(file_heading_slugs(lines)), frozenset(file_anchor_ids(lines)))


def _is_glossary(path: Path, repo_root: Path) -> bool:
    """Return whether ``path`` is one of the two glossaries of ``repo_root``."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix() in GLOSSARY_PATHS
    except ValueError:
        return False


def _anchor_problem(anchor: str, anchors: FileAnchors, *, glossary: bool, display_target: str) -> str | None:
    """Return why ``#anchor`` does not resolve in a file, or ``None`` when it does."""
    if anchor in anchors.ids:
        return None
    if glossary:
        if anchor in anchors.slugs:
            return f"#{anchor} is a heading slug in {display_target}; link the entry's <a id> instead"
        return f"no entry id produces anchor #{anchor} in {display_target}"
    if anchor in anchors.slugs:
        return None
    return f"no heading produces anchor #{anchor} in {display_target}"


def _is_external(target: str) -> bool:
    return bool(_SCHEME_RE.match(target)) or target.startswith("//")


def find_broken_links_in_file(
    source_file: Path,
    lines: list[str],
    *,
    repo_root: Path,
    heading_slug_cache: dict[Path, FileAnchors],
) -> list[BrokenLink]:
    """Return every broken local link/anchor found in one file's lines.

    A same-file ``#anchor`` link is checked against ``lines`` directly rather
    than by re-reading ``source_file`` from disk, since the caller may be
    checking content that has not been written to disk yet (as the tests do)
    and re-reading the file currently being processed is redundant besides.
    """
    broken: list[BrokenLink] = []
    for line_number, line in iter_non_fenced_lines(lines):
        searchable_line = _INLINE_CODE_SPAN_RE.sub(" ", line)
        for match in _LINK_RE.finditer(searchable_line):
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
                anchors = file_anchors(lines)
                display_target = "this file"
                glossary = _is_glossary(source_file, repo_root)
            else:
                if target_file not in heading_slug_cache:
                    target_lines = target_file.read_text(encoding="utf-8").splitlines(keepends=True)
                    heading_slug_cache[target_file] = file_anchors(target_lines)
                anchors = heading_slug_cache[target_file]
                display_target = str(target_file.relative_to(repo_root))
                glossary = _is_glossary(target_file, repo_root)
            reason = _anchor_problem(anchor, anchors, glossary=glossary, display_target=display_target)
            if reason is not None:
                broken.append(BrokenLink(source_file, line_number, link_text, target, reason))
    return broken


def list_tracked_markdown_files(repo_root: Path) -> list[Path]:
    """Return the absolute path of every ``.md`` file git tracks, plus every untracked one it does not ignore.

    A new document is checked before it is staged; a file matched by ``.gitignore`` is skipped.
    """
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.md"],
        cwd=repo_root,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    paths = dict.fromkeys(repo_root / line for line in output.splitlines() if line)
    return [path for path in paths if path.is_file()]


def check_repository(repo_root: Path) -> list[BrokenLink]:
    """Check every tracked or untracked-and-unignored Markdown file in ``repo_root`` and return all breaks found."""
    heading_slug_cache: dict[Path, FileAnchors] = {}
    broken: list[BrokenLink] = []
    for markdown_file in list_tracked_markdown_files(repo_root):
        lines = markdown_file.read_text(encoding="utf-8").splitlines(keepends=True)
        broken.extend(
            find_broken_links_in_file(markdown_file, lines, repo_root=repo_root, heading_slug_cache=heading_slug_cache)
        )
    return broken


def check_repository_diagrams(repo_root: Path) -> list[MermaidBlock]:
    """Return every Mermaid block in the Markdown files of ``repo_root``."""
    found: list[MermaidBlock] = []
    for markdown_file in list_tracked_markdown_files(repo_root):
        lines = markdown_file.read_text(encoding="utf-8").splitlines(keepends=True)
        found.extend(find_mermaid_blocks_in_file(markdown_file, lines))
    return found


def check_repository_commands(repo_root: Path) -> list[BareIanCommand]:
    """Return every bare ``ian`` command in the fenced blocks of the user documentation and README of ``repo_root``."""
    found: list[BareIanCommand] = []
    for markdown_file in list_tracked_markdown_files(repo_root):
        relative = markdown_file.relative_to(repo_root).as_posix()
        if relative != USER_README and not relative.startswith(USER_DOCUMENT_PREFIX):
            continue
        lines = markdown_file.read_text(encoding="utf-8").splitlines(keepends=True)
        found.extend(find_bare_ian_commands_in_file(markdown_file, lines))
    return found


def main() -> int:
    """Check the repository this script lives in; print every break; return the process exit code."""
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True, text=True
        ).stdout.strip()
    )
    broken_links = check_repository(repo_root)
    mermaid_blocks = check_repository_diagrams(repo_root)
    bare_commands = check_repository_commands(repo_root)
    if not broken_links and not mermaid_blocks and not bare_commands:
        print("check_doc_links: no broken local links or anchors, no Mermaid blocks and no bare ian commands found.")
        return 0
    for broken in broken_links:
        print(broken)
    for block in mermaid_blocks:
        print(block)
    for command in bare_commands:
        print(command)
    print(
        f"check_doc_links: {len(broken_links)} broken local link(s)/anchor(s), "
        f"{len(mermaid_blocks)} Mermaid block(s) and {len(bare_commands)} bare ian command(s) found.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
