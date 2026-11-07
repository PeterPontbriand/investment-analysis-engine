"""Checker for the structure of the two glossaries.

Both glossaries, ``docs/user/GLOSSARY.md`` (investor terms, plus one command-line section) and
``docs/project/CONTRIBUTOR_GLOSSARY.md`` (contributor terms), are written so that each entry can be served on its own.
An entry is a level-3 heading. For every entry the checker requires:

- an id line, ``<a id="<id>"></a>``, on its own line directly above the heading;
- an id of lowercase ASCII words joined by single hyphens, unique within its glossary, and not equal to the heading slug
  of a different entry (the heading slug is what GitHub generates, and a link to it is refused by
  ``scripts/check_doc_links.py``);
- a name, the heading text, that is plain text: no code span, link, emphasis or bracket;
- a short definition, the first paragraph after the heading: at most 200 characters and two sentences, and plain text
  (no link, backtick, ``*``, ``_`` or ``[``).

Whether a short definition stands alone is a review rule, not a checked one.

``<!-- help:exclude -->`` on the line directly after a heading excludes that section, with its subsections, from served
content. An entry inside an excluded section of the user glossary is a command-line term. The checker refuses a marker
anywhere else, and refuses a link from an investor entry (an entry of the user glossary outside an excluded
section) to a contributor term or to a command-line term.

Only the standard library is used, so the checker runs with system Python.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path


@cache
def git_repository_root() -> Path:
    """Return the repository root that git reports; asked once."""
    return Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True, text=True
        ).stdout.strip()
    )


if __package__ in (None, ""):
    # Run as ``python scripts/check_help_content.py``: the repository root is not on the path yet.
    sys.path.insert(0, str(git_repository_root()))

from scripts.check_doc_links import ANCHOR_ID_RE, GLOSSARY_PATHS, slugify  # noqa: E402

USER_GLOSSARY = GLOSSARY_PATHS[0]
CONTRIBUTOR_GLOSSARY = GLOSSARY_PATHS[1]
EXCLUDE_MARKER = "<!-- help:exclude -->"
ENTRY_LEVEL = 3
MAX_DEFINITION_CHARACTERS = 200
MAX_DEFINITION_PARTS = 2
_PLAIN_TEXT_FORBIDDEN = "`*_["
_ID_RE = re.compile(r"^[a-z]+(-[a-z]+)*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^(```+|~~~+)")
_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"(?<!`)(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)")
_DEFINITION_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


@dataclass(frozen=True)
class Problem:
    """One violation of the glossary rules."""

    source_file: str
    line_number: int
    entry: str
    reason: str

    def __str__(self) -> str:
        """Render as ``path:line: entry 'name' -- reason``."""
        subject = f"entry '{self.entry}'" if self.entry else "file"
        return f"{self.source_file}:{self.line_number}: {subject} -- {self.reason}"


@dataclass(frozen=True)
class Entry:
    """One glossary entry as the checker reads it."""

    name: str
    heading_line: int
    anchor_id: str | None
    excluded: bool
    short_definition: str | None
    link_targets: tuple[str, ...]


@dataclass(frozen=True)
class ParsedGlossary:
    """The entries of one glossary file and the exclude markers that are not on a heading's next line."""

    entries: tuple[Entry, ...]
    stray_marker_lines: tuple[int, ...]


def _first_paragraph(lines: list[str], start: int, end: int) -> str | None:
    """Return the text of the first paragraph in ``lines[start:end]``, or ``None`` when it is not prose."""
    index = start
    while index < end and not lines[index].strip():
        index += 1
    if index >= end or _FENCE_RE.match(lines[index].strip()):
        return None
    parts: list[str] = []
    while index < end and lines[index].strip() and not _FENCE_RE.match(lines[index].strip()):
        parts.append(lines[index].strip())
        index += 1
    return " ".join(parts)


def _links_in(lines: list[str]) -> tuple[str, ...]:
    """Return the target of every inline link in ``lines``, skipping fenced blocks and code spans."""
    targets: list[str] = []
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        searchable = _INLINE_CODE_RE.sub(" ", line)
        targets.extend(match.group(1).strip() for match in _LINK_RE.finditer(searchable))
    return tuple(targets)


def parse_glossary(lines: list[str]) -> ParsedGlossary:
    """Read the entries of one glossary file from its lines."""
    stripped = [line.rstrip("\n") for line in lines]
    headings: list[tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(stripped):
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2)))
    marker_after_heading = {
        index + 1
        for index, _level, _text in headings
        if index + 1 < len(stripped) and stripped[index + 1].strip() == EXCLUDE_MARKER
    }
    stray = tuple(
        number
        for number, line in enumerate(stripped, start=1)
        if line.strip() == EXCLUDE_MARKER and number - 1 not in marker_after_heading
    )
    entries: list[Entry] = []
    excluded_level: int | None = None
    for position, (index, level, text) in enumerate(headings):
        if excluded_level is not None and level <= excluded_level:
            excluded_level = None
        has_marker = (index + 1) in marker_after_heading
        if has_marker and excluded_level is None:
            excluded_level = level
        if level != ENTRY_LEVEL:
            continue
        end = headings[position + 1][0] if position + 1 < len(headings) else len(stripped)
        body_start = index + 2 if has_marker else index + 1
        anchor_id = None
        if index > 0:
            above = ANCHOR_ID_RE.match(stripped[index - 1].strip())
            anchor_id = above.group(1) if above else None
        entries.append(
            Entry(
                name=text,
                heading_line=index + 1,
                anchor_id=anchor_id,
                excluded=excluded_level is not None,
                short_definition=_first_paragraph(stripped, body_start, end),
                link_targets=_links_in(stripped[body_start:end]),
            )
        )
    return ParsedGlossary(tuple(entries), stray)


def _definition_problems(definition: str) -> list[str]:
    """Return what is wrong with one short definition."""
    problems: list[str] = []
    if len(definition) > MAX_DEFINITION_CHARACTERS:
        problems.append(f"short definition is {len(definition)} characters; the limit is {MAX_DEFINITION_CHARACTERS}")
    parts = [part for part in _DEFINITION_SPLIT_RE.split(definition) if part.strip()]
    if len(parts) > MAX_DEFINITION_PARTS:
        problems.append(f"short definition has {len(parts)} sentences; the limit is {MAX_DEFINITION_PARTS}")
    found = sorted({character for character in definition if character in _PLAIN_TEXT_FORBIDDEN})
    if found:
        problems.append(
            "short definition is not plain text: it contains " + " ".join(repr(character) for character in found)
        )
    return problems


def _resolve(relative_path: str, target: str, repo_root: Path) -> tuple[str | None, str]:
    """Return the repository-relative path a link in ``relative_path`` names (``None`` when external) and its anchor."""
    if _SCHEME_RE.match(target) or target.startswith("//"):
        return None, ""
    path_part, _, anchor = target.partition("#")
    if not path_part:
        return relative_path, anchor
    resolved = (repo_root / Path(relative_path).parent / path_part).resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix(), anchor
    except ValueError:
        return None, anchor


def _id_problems(entry: Entry, parsed: ParsedGlossary, first_by_id: dict[str, Entry]) -> list[str]:
    """Return what is wrong with one entry's id; records the id in ``first_by_id``."""
    anchor_id = entry.anchor_id
    if anchor_id is None:
        return ['no id line directly above the heading; expected <a id="..."></a> on its own line']
    problems: list[str] = []
    if not _ID_RE.match(anchor_id):
        problems.append(f"id {anchor_id!r} is not lowercase ASCII words joined by single hyphens")
    if anchor_id in first_by_id:
        other = first_by_id[anchor_id]
        problems.append(f"id {anchor_id!r} is already the id of entry '{other.name}' (line {other.heading_line})")
    else:
        first_by_id[anchor_id] = entry
    problems.extend(
        f"id {anchor_id!r} is the heading slug of a different entry, '{other.name}'"
        for other in parsed.entries
        if other is not entry and slugify(other.name) == anchor_id
    )
    return problems


def _link_problems(entry: Entry, relative_path: str, command_line_ids: frozenset[str], repo_root: Path) -> list[str]:
    """Return the links of an investor entry that reach a contributor or command-line term."""
    problems: list[str] = []
    for target in entry.link_targets:
        path, anchor = _resolve(relative_path, target, repo_root)
        if path == CONTRIBUTOR_GLOSSARY:
            problems.append(f"investor entry links to a contributor term: {target}")
        elif path == USER_GLOSSARY and anchor in command_line_ids:
            problems.append(f"investor entry links to a command-line term: {target}")
    return problems


def _entry_problems(entry: Entry, parsed: ParsedGlossary, first_by_id: dict[str, Entry]) -> list[str]:
    """Return every problem of one entry except its links."""
    reasons = [
        f"the name is not plain text: it contains {character!r}"
        for character in sorted({character for character in entry.name if character in _PLAIN_TEXT_FORBIDDEN})
    ]
    reasons.extend(_id_problems(entry, parsed, first_by_id))
    if entry.short_definition is None:
        reasons.append("no short definition: the first paragraph after the heading is missing or is not prose")
    else:
        reasons.extend(_definition_problems(entry.short_definition))
    return reasons


def check_glossary(
    relative_path: str, lines: list[str], *, command_line_ids: frozenset[str] = frozenset(), repo_root: Path
) -> list[Problem]:
    """Return every problem in one glossary file.

    ``command_line_ids`` holds the ids of the user glossary's command-line terms; it matters only to the user glossary's
    investor entries, which may not link to them.
    """
    parsed = parse_glossary(lines)
    problems = [
        Problem(relative_path, line_number, "", f"{EXCLUDE_MARKER} must be on the line directly after a heading")
        for line_number in parsed.stray_marker_lines
    ]
    first_by_id: dict[str, Entry] = {}
    for entry in parsed.entries:
        reasons = _entry_problems(entry, parsed, first_by_id)
        if relative_path == USER_GLOSSARY and not entry.excluded:
            reasons.extend(_link_problems(entry, relative_path, command_line_ids, repo_root))
        problems.extend(Problem(relative_path, entry.heading_line, entry.name, reason) for reason in reasons)
    return problems


def command_line_ids_of(lines: list[str]) -> frozenset[str]:
    """Return the ids of the entries inside an excluded section of the user glossary."""
    return frozenset(
        entry.anchor_id for entry in parse_glossary(lines).entries if entry.excluded and entry.anchor_id is not None
    )


def check_repository(repo_root: Path) -> list[Problem]:
    """Check both glossaries of ``repo_root`` and return every problem."""
    problems: list[Problem] = []
    texts: dict[str, list[str]] = {}
    for relative in GLOSSARY_PATHS:
        path = repo_root / relative
        if not path.is_file():
            problems.append(Problem(relative, 0, "", "the glossary file does not exist"))
            continue
        texts[relative] = path.read_text(encoding="utf-8").splitlines(keepends=True)
    command_line_ids = command_line_ids_of(texts[USER_GLOSSARY]) if USER_GLOSSARY in texts else frozenset()
    for relative, lines in texts.items():
        problems.extend(check_glossary(relative, lines, command_line_ids=command_line_ids, repo_root=repo_root))
    return problems


def main() -> int:
    """Check the repository this script lives in; print every problem; return the process exit code."""
    repo_root = git_repository_root()
    problems = check_repository(repo_root)
    if not problems:
        print("check_help_content: both glossaries follow the entry rules.")
        return 0
    for found in problems:
        print(found)
    print(f"check_help_content: {len(problems)} problem(s) found.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
