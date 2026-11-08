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

The documents the help bundle serves are the Beginner Guide, Finance Math, the user glossary and every strategy guide.
Their served content (``served_documents``) fails the check on any of:

- a code span that starts with ``ian ``, ``--``, ``uv `` or ``IAN_``;
- a fenced block that holds an ``ian`` command line, or whose language is a shell;
- a link to a repository file that is not served, to an excluded section of a served document, to a term that is not
  served, or to the user glossary without an entry id.

An external link passes. A served document has exactly one level-1 heading, its title. A heading titled
``On the command line`` must carry the exclude marker and be the last subsection of its parent.
``tests/scripts/test_served_content.py`` adds the check that no code span starts with the name of an ``ian``
command, a name read from the application and not listed here.

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
GROUP_LEVEL = 2
MAX_DEFINITION_CHARACTERS = 200
MAX_DEFINITION_PARTS = 2
_PLAIN_TEXT_FORBIDDEN = "`*_["
SERVED_DOCUMENT_PATHS = ("docs/user/BEGINNER_GUIDE.md", "docs/user/FINANCE_MATH.md", USER_GLOSSARY)
STRATEGY_GUIDE_DIRECTORY = "docs/user/strategies"
STRATEGY_INDEX = "README.md"
COMMAND_LINE_HEADING = "On the command line"
FORBIDDEN_SPAN_PREFIXES = ("ian ", "--", "uv ", "IAN_")
SHELL_LANGUAGES = frozenset({"bash", "sh", "shell", "console", "powershell", "pwsh", "ps1", "cmd"})
CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_IAN_COMMAND_LINE_RE = re.compile(r"^(?:uv\s+run\s+)?ian(?:\s|$)")
_ID_RE = re.compile(r"^[a-z]+(-[a-z]+)*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^(```+|~~~+)")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"(?<!`)(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)")
_DEFINITION_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


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
    if index >= end or FENCE_RE.match(lines[index].strip()):
        return None
    parts: list[str] = []
    while index < end and lines[index].strip() and not FENCE_RE.match(lines[index].strip()):
        parts.append(lines[index].strip())
        index += 1
    return " ".join(parts)


def _links_in(lines: list[str]) -> tuple[str, ...]:
    """Return the target of every inline link in ``lines``, skipping fenced blocks and code spans."""
    targets: list[str] = []
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        searchable = _INLINE_CODE_RE.sub(" ", line)
        targets.extend(match.group(1).strip() for match in LINK_RE.finditer(searchable))
    return tuple(targets)


def parse_glossary(lines: list[str]) -> ParsedGlossary:
    """Read the entries of one glossary file from its lines."""
    stripped = [line.rstrip("\n") for line in lines]
    headings: list[tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(stripped):
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
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
    if SCHEME_RE.match(target) or target.startswith("//"):
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


@dataclass(frozen=True)
class ServedSection:
    """One non-excluded section of a served document.

    ``first_line`` is the heading's 1-based line number and ``last_line`` the section's last line; the section ends
    at the next heading of any level, so a subsection is a section of its own. ``lines`` is the text after the
    heading, with its line endings removed. ``anchor_id`` is the id line above the heading, when there is one, and
    ``slug`` is the heading's GitHub anchor, which counts every heading of the file, excluded ones included.
    """

    heading: str
    level: int
    first_line: int
    last_line: int
    lines: tuple[str, ...]
    anchor_id: str | None
    slug: str

    @property
    def body_first_line(self) -> int:
        """Return the 1-based line number of the first line of ``lines``."""
        return self.first_line + 1


@dataclass(frozen=True)
class ServedGroup:
    """One level-2 heading of the user glossary, which groups the entries under it.

    ``line`` is the heading's 1-based line number and ``slug`` its GitHub anchor, counting every heading of the file.
    ``excluded`` is whether the heading carries the exclude marker itself.
    """

    heading: str
    line: int
    slug: str
    excluded: bool


@dataclass(frozen=True)
class ServedDocument:
    """A served document: its repository-relative path, its title and its non-excluded sections, in file order.

    ``groups`` holds the level-2 headings of the user glossary, in file order, excluded ones included; it is empty
    for every other document.
    """

    path: str
    title: str
    sections: tuple[ServedSection, ...]
    groups: tuple[ServedGroup, ...] = ()


@dataclass(frozen=True)
class ContentProblem:
    """One violation of the served-content rules."""

    source_file: str
    line_number: int
    section: str
    reason: str

    def __str__(self) -> str:
        """Render as ``path:line: section 'heading' -- reason``."""
        return f"{self.source_file}:{self.line_number}: section '{self.section}' -- {self.reason}"


@dataclass(frozen=True)
class _Heading:
    index: int
    level: int
    text: str
    marked: bool
    excluded: bool
    slug: str


@dataclass(frozen=True)
class _ParsedDocument:
    lines: tuple[str, ...]
    headings: tuple[_Heading, ...]
    stray_marker_lines: tuple[int, ...]


def _parse_document(raw_lines: list[str]) -> _ParsedDocument:
    """Find the headings of a document, which are excluded, and the markers not on a heading's next line."""
    lines = tuple(line.rstrip("\n") for line in raw_lines)
    found: list[tuple[int, int, str]] = []
    fence_marker: str | None = None
    for index, line in enumerate(lines):
        fence = FENCE_RE.match(line.strip())
        if fence:
            if fence_marker is None:
                fence_marker = fence.group(1)[0] * 3
            elif line.strip().startswith(fence_marker):
                fence_marker = None
            continue
        match = None if fence_marker else HEADING_RE.match(line)
        if match:
            found.append((index, len(match.group(1)), match.group(2)))
    marked = {
        index for index, _level, _text in found if index + 1 < len(lines) and lines[index + 1].strip() == EXCLUDE_MARKER
    }
    stray = tuple(
        number
        for number, line in enumerate(lines, start=1)
        if line.strip() == EXCLUDE_MARKER and (number - 2) not in marked
    )
    headings: list[_Heading] = []
    seen: dict[str, int] = {}
    excluded_level: int | None = None
    for index, level, text in found:
        if excluded_level is not None and level <= excluded_level:
            excluded_level = None
        if index in marked and excluded_level is None:
            excluded_level = level
        base = slugify(text)
        count = seen.get(base, 0)
        if base:
            seen[base] = count + 1
        slug = base if count == 0 else f"{base}-{count}"
        headings.append(_Heading(index, level, text, index in marked, excluded_level is not None, slug))
    return _ParsedDocument(lines, tuple(headings), stray)


def _section_of(parsed: _ParsedDocument, position: int) -> ServedSection:
    """Return the section that starts at heading number ``position``, without its trailing id line."""
    heading = parsed.headings[position]
    end = parsed.headings[position + 1].index if position + 1 < len(parsed.headings) else len(parsed.lines)
    body = list(parsed.lines[heading.index + 1 : end])
    while body and not body[-1].strip():
        body.pop()
    if body and ANCHOR_ID_RE.match(body[-1].strip()):
        body.pop()
        while body and not body[-1].strip():
            body.pop()
    above = ANCHOR_ID_RE.match(parsed.lines[heading.index - 1].strip()) if heading.index > 0 else None
    return ServedSection(
        heading=heading.text,
        level=heading.level,
        first_line=heading.index + 1,
        last_line=heading.index + 1 + len(body),
        lines=tuple(body),
        anchor_id=above.group(1) if above else None,
        slug=heading.slug,
    )


def served_document(relative_path: str, raw_lines: list[str]) -> ServedDocument:
    """Return the served content of one document from its lines.

    The user glossary serves the text of each entry (a level-3 section) outside an excluded section; its
    introduction and section headings are not served. Any other document serves every section outside an
    excluded section, the text under its title included.
    """
    parsed = _parse_document(raw_lines)
    glossary = relative_path == USER_GLOSSARY
    sections = tuple(
        _section_of(parsed, position)
        for position, heading in enumerate(parsed.headings)
        if not heading.excluded and (heading.level == ENTRY_LEVEL if glossary else True)
    )
    title = next((heading.text for heading in parsed.headings if heading.level == 1), Path(relative_path).stem)
    groups = tuple(
        ServedGroup(heading.text, heading.index + 1, heading.slug, heading.marked)
        for heading in parsed.headings
        if glossary and heading.level == GROUP_LEVEL
    )
    return ServedDocument(relative_path, title, sections, groups)


def strategy_guide_paths(repo_root: Path) -> tuple[str, ...]:
    """Return the repository-relative path of every strategy guide, which is every file of the folder but its index."""
    folder = repo_root / STRATEGY_GUIDE_DIRECTORY
    return tuple(
        f"{STRATEGY_GUIDE_DIRECTORY}/{path.name}" for path in sorted(folder.glob("*.md")) if path.name != STRATEGY_INDEX
    )


def served_paths(repo_root: Path) -> tuple[str, ...]:
    """Return the repository-relative path of every served document."""
    return (*SERVED_DOCUMENT_PATHS, *strategy_guide_paths(repo_root))


def served_documents(repo_root: Path) -> tuple[ServedDocument, ...]:
    """Return the served content of every served document that exists in ``repo_root``."""
    return tuple(
        served_document(relative, (repo_root / relative).read_text(encoding="utf-8").splitlines(keepends=True))
        for relative in served_paths(repo_root)
        if (repo_root / relative).is_file()
    )


@dataclass(frozen=True)
class _LinkContext:
    """What a link in served content is checked against."""

    served: frozenset[str]
    term_ids: frozenset[str]
    excluded_slugs: dict[str, frozenset[str]]
    repo_root: Path


def _link_reason(relative_path: str, target: str, context: _LinkContext) -> str | None:
    """Return why a link in served content is refused, or ``None`` when it passes."""
    target = target.split(maxsplit=1)[0] if target.split() else target
    path, anchor = _resolve(relative_path, target, context.repo_root)
    if path is None:
        outside = not (SCHEME_RE.match(target) or target.startswith("//"))
        return f"link to a file outside the repository: {target}" if outside else None
    if path not in context.served:
        return f"link to a repository file that is not served: {target}"
    if path == USER_GLOSSARY:
        if not anchor:
            return f"link to {USER_GLOSSARY} with no entry id: {target}"
        if anchor not in context.term_ids:
            return f"link to a term that is not served: {target}"
    elif anchor in context.excluded_slugs.get(path, frozenset()):
        return f"link to an excluded section of a served document: {target}"
    return None


def _text_and_numbers(paragraph: list[tuple[int, str]]) -> tuple[str, list[int]]:
    """Return the text of one paragraph and the line number of each of its lines."""
    return "\n".join(line for _number, line in paragraph), [number for number, _line in paragraph]


def _paragraph_code_spans(paragraph: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Return ``(line, content)`` for each code span of one paragraph; the content has single spaces."""
    text, numbers = _text_and_numbers(paragraph)
    return [
        (numbers[text.count("\n", 0, span.start())], " ".join(span.group(2).split()))
        for span in CODE_SPAN_RE.finditer(text)
    ]


def _paragraph_problems(
    paragraph: list[tuple[int, str]], relative_path: str, context: _LinkContext
) -> list[tuple[int, str]]:
    """Return ``(line, reason)`` for the code spans and links of one paragraph of prose."""
    text, numbers = _text_and_numbers(paragraph)
    found = [
        (number, f"code span starts with {prefix!r}: `{content}`")
        for number, content in _paragraph_code_spans(paragraph)
        for prefix in FORBIDDEN_SPAN_PREFIXES
        if content.startswith(prefix)
    ]
    blanked = CODE_SPAN_RE.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)
    for link in LINK_RE.finditer(blanked):
        reason = _link_reason(relative_path, link.group(1).strip(), context)
        if reason:
            found.append((numbers[blanked.count("\n", 0, link.start())], reason))
    return found


def _walk_section(section: ServedSection) -> tuple[list[list[tuple[int, str]]], list[tuple[int, str]]]:
    """Split a section into its paragraphs of prose and the problems of its fenced blocks.

    A paragraph is a list of ``(line, text)``; a problem is ``(line, reason)``.
    """
    paragraphs: list[list[tuple[int, str]]] = []
    problems: list[tuple[int, str]] = []
    paragraph: list[tuple[int, str]] = []
    fence_marker: str | None = None
    for offset, raw in enumerate(section.lines):
        number = section.body_first_line + offset
        stripped = raw.strip()
        fence = FENCE_RE.match(stripped)
        if fence:
            paragraphs.append(paragraph)
            paragraph = []
            if fence_marker is None:
                fence_marker = fence.group(1)[0] * 3
                language = stripped[len(fence.group(1)) :].split(maxsplit=1)
                if language and language[0].lower() in SHELL_LANGUAGES:
                    problems.append((number, f"fenced block in a shell language: {language[0]}"))
            elif stripped.startswith(fence_marker):
                fence_marker = None
            continue
        if fence_marker is not None:
            if _IAN_COMMAND_LINE_RE.match(stripped):
                problems.append((number, f"fenced block holds an ian command line: {stripped}"))
        elif stripped:
            paragraph.append((number, raw))
        else:
            paragraphs.append(paragraph)
            paragraph = []
    paragraphs.append(paragraph)
    return [item for item in paragraphs if item], problems


def code_spans(section: ServedSection) -> list[tuple[int, str]]:
    """Return ``(line, content)`` for every code span in the prose of a section, fenced blocks excluded."""
    return [span for paragraph in _walk_section(section)[0] for span in _paragraph_code_spans(paragraph)]


def _section_problems(section: ServedSection, relative_path: str, context: _LinkContext) -> list[ContentProblem]:
    """Return every leak in the text of one served section."""
    paragraphs, found = _walk_section(section)
    for paragraph in paragraphs:
        found.extend(_paragraph_problems(paragraph, relative_path, context))
    return [ContentProblem(relative_path, number, section.heading, reason) for number, reason in sorted(found)]


def _structure_problems(relative_path: str, raw_lines: list[str]) -> list[ContentProblem]:
    """Return the problems of a document's level-1 headings, exclude markers and "On the command line" subsections."""
    parsed = _parse_document(raw_lines)
    found = [
        ContentProblem(relative_path, number, "", f"{EXCLUDE_MARKER} must be on the line directly after a heading")
        for number in parsed.stray_marker_lines
    ]
    titles = [heading for heading in parsed.headings if heading.level == 1]
    if len(titles) != 1:
        found.append(
            ContentProblem(
                relative_path,
                titles[0].index + 1 if titles else 0,
                "",
                f"a served document must have exactly one level-1 heading; found {len(titles)}",
            )
        )
    for position, heading in enumerate(parsed.headings):
        line = heading.index + 1
        if heading.marked and heading.level == 1:
            found.append(ContentProblem(relative_path, line, heading.text, "the document title cannot be excluded"))
        if heading.text != COMMAND_LINE_HEADING:
            continue
        if not heading.marked:
            found.append(
                ContentProblem(
                    relative_path,
                    line,
                    heading.text,
                    f"a section titled {COMMAND_LINE_HEADING!r} must carry {EXCLUDE_MARKER}",
                )
            )
        following = next((item for item in parsed.headings[position + 1 :] if item.level <= heading.level), None)
        if following is not None and following.level == heading.level:
            found.append(
                ContentProblem(
                    relative_path,
                    line,
                    heading.text,
                    f"a section titled {COMMAND_LINE_HEADING!r} must be the last subsection of its parent; "
                    f"'{following.text}' follows it",
                )
            )
    return found


def check_served_content(repo_root: Path) -> list[ContentProblem]:
    """Check the served documents of ``repo_root`` and return every problem."""
    problems: list[ContentProblem] = []
    texts: dict[str, list[str]] = {}
    for relative in served_paths(repo_root):
        path = repo_root / relative
        if not path.is_file():
            problems.append(ContentProblem(relative, 0, "", "the served document does not exist"))
            continue
        texts[relative] = path.read_text(encoding="utf-8").splitlines(keepends=True)
    documents = [served_document(relative, lines) for relative, lines in texts.items()]
    term_ids = frozenset(
        section.anchor_id
        for document in documents
        if document.path == USER_GLOSSARY
        for section in document.sections
        if section.anchor_id is not None
    )
    excluded_slugs = {
        relative: frozenset(heading.slug for heading in _parse_document(lines).headings if heading.excluded)
        for relative, lines in texts.items()
    }
    context = _LinkContext(frozenset(texts), term_ids, excluded_slugs, repo_root)
    for relative, lines in texts.items():
        problems.extend(_structure_problems(relative, lines))
    for document in documents:
        for section in document.sections:
            problems.extend(_section_problems(section, document.path, context))
    return problems


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
    problems = [*check_repository(repo_root), *check_served_content(repo_root)]
    if not problems:
        print("check_help_content: both glossaries follow the entry rules and the served content has no leak.")
        return 0
    for found in problems:
        print(found)
    print(f"check_help_content: {len(problems)} problem(s) found.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
