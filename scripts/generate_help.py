"""Generate the help bundle of the served documents, or check it for drift.

The bundle is built from the served documents that ``scripts/check_help_content.py`` finds: the investor entries of the
user glossary become terms, grouped by the glossary's sections, and the Beginner Guide, Finance Math and each strategy
guide become documents of sections. Links between served content become ``help:`` links. The bundle is built through
``HelpBundle``, so its integrity checks apply before anything is written, and it is written to
``investment_analysis_engine/help/help_bundle.json`` with sorted keys, two-space indent and a trailing line feed.

Both writing and ``--check`` first run the served-content check; if it reports any problem, every problem is printed and
nothing is written or compared.

Usage, as a module from the repository root::

    uv run python -m scripts.generate_help          # write the bundle
    uv run python -m scripts.generate_help --check  # report a bundle that is missing or out of date

This is a developer script, not an ``ian`` command.
"""

import argparse
import json
import posixpath
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from investment_analysis_engine.help.bundle import (
    DOCUMENT_LINK_PREFIX,
    TERM_LINK_PREFIX,
    HelpBundle,
    HelpDocument,
    HelpGroup,
    HelpSection,
    HelpTerm,
)
from investment_analysis_engine.strategy_wiring import STRATEGIES
from scripts.check_doc_links import slugify
from scripts.check_help_content import (
    EXCLUDE_MARKER,
    STRATEGY_GUIDE_DIRECTORY,
    USER_GLOSSARY,
    ServedDocument,
    check_served_content,
    served_documents,
)
from scripts.generate_strategy_docs import guide_name
from scripts.repository_root import REPOSITORY_ROOT

HELP_BUNDLE_FILE = REPOSITORY_ROOT / "investment_analysis_engine" / "help" / "help_bundle.json"
REGENERATE_COMMAND = "uv run python -m scripts.generate_help"
GLOSSARY_GROUP_LEVEL = 2
FIXED_DOCUMENT_IDS = {
    "docs/user/BEGINNER_GUIDE.md": "beginner-guide",
    "docs/user/FINANCE_MATH.md": "finance-math",
}

_FENCE_RE = re.compile(r"^(```+|~~~+)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_THEMATIC_BREAK_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


class HelpGenerationError(ValueError):
    """The served content cannot be turned into a bundle; the message names the file, the line and the cause."""


@dataclass(frozen=True)
class LinkContext:
    """What a link in served content is resolved against.

    ``document_ids`` maps the repository-relative path of each served document that becomes a bundle document to its
    id, and ``title_slugs`` maps the same paths to the slug of the document's level-1 heading.
    """

    document_ids: Mapping[str, str]
    title_slugs: Mapping[str, str]


def _mask_code(text: str) -> str:
    """Return ``text`` with fenced blocks and code spans blanked to spaces, keeping every position and line break."""
    lines: list[str] = []
    fence_marker: str | None = None
    for line in text.split("\n"):
        fence = _FENCE_RE.match(line.strip())
        if fence and fence_marker is None:
            fence_marker = fence.group(1)[0] * 3
            lines.append(" " * len(line))
        elif fence_marker is not None:
            if fence and line.strip().startswith(fence_marker):
                fence_marker = None
            lines.append(" " * len(line))
        else:
            lines.append(line)
    masked = "\n".join(lines)
    return _CODE_SPAN_RE.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), masked)


def _resolve_target(source: str, target: str) -> tuple[str, str] | None:
    """Return the repository-relative path and the anchor a relative link names, or ``None`` when it is not one."""
    if _SCHEME_RE.match(target) or target.startswith("//"):
        return None
    path_part, _, anchor = target.partition("#")
    if not path_part:
        return source, anchor
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path_part))
    return None if resolved.startswith("..") else (resolved, anchor)


def _bundle_link(source: str, target: str, context: LinkContext) -> str | None:
    """Return the bundle link for ``target`` written in ``source``; ``None`` when no row of the rewrite table fits."""
    if target.startswith("https://"):
        return target
    named = _resolve_target(source, target)
    if named is None:
        return None
    resolved, anchor = named
    if resolved == USER_GLOSSARY:
        return f"{TERM_LINK_PREFIX}{anchor}" if anchor else None
    document_id = context.document_ids.get(resolved)
    if document_id is None:
        return None
    if not anchor or anchor == context.title_slugs[resolved]:
        return f"{DOCUMENT_LINK_PREFIX}{document_id}"
    return f"{DOCUMENT_LINK_PREFIX}{document_id}#{anchor}"


def rewrite_links(lines: Sequence[str], first_line: int, source: str, context: LinkContext) -> list[str]:
    """Return ``lines`` with every link target rewritten to its bundle form; only the target changes.

    ``first_line`` is the 1-based line number of ``lines[0]`` in ``source``, the repository-relative path of the file
    the lines come from. Links inside fenced blocks and code spans are left as written. A link that fits no row of the
    rewrite table raises ``HelpGenerationError`` naming the file, the line and the target.
    """
    text = "\n".join(lines)
    masked = _mask_code(text)
    pieces: list[str] = []
    position = 0
    for match in _LINK_RE.finditer(masked):
        raw = text[match.start(1) : match.end(1)]
        if not raw.split():
            continue
        offset = match.start(1) + (len(raw) - len(raw.lstrip()))
        target = raw.split(maxsplit=1)[0]
        replacement = _bundle_link(source, target, context)
        if replacement is None:
            line = first_line + text.count("\n", 0, offset)
            raise HelpGenerationError(f"{source}:{line}: the link target {target!r} fits no rewrite rule")
        pieces.append(text[position:offset])
        pieces.append(replacement)
        position = offset + len(target)
    pieces.append(text[position:])
    return "".join(pieces).split("\n")


def trim(lines: Sequence[str]) -> str:
    """Return ``lines`` as text without leading or trailing blank lines or a trailing thematic break."""
    items = list(lines)
    while items and not items[0].strip():
        items.pop(0)
    while items and not items[-1].strip():
        items.pop()
    if items and _THEMATIC_BREAK_RE.match(items[-1].strip()):
        items.pop()
        while items and not items[-1].strip():
            items.pop()
    return "\n".join(items)


def _split_entry(lines: Sequence[str]) -> tuple[str, str] | None:
    """Return an entry's short definition (its first paragraph) and the rest, or ``None`` when it has no paragraph."""
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and lines[end].strip():
        end += 1
    if start == end:
        return None
    return " ".join(line.strip() for line in lines[start:end]), trim(lines[end:])


@dataclass(frozen=True)
class _GlossaryGroup:
    """A level-2 heading of the user glossary: where it is, its text and slug, and whether it is excluded."""

    line: int
    title: str
    slug: str
    excluded: bool


def _glossary_groups(raw_lines: Sequence[str]) -> list[_GlossaryGroup]:
    """Return the glossary's level-2 headings, with GitHub's slugs counted over every heading of the file."""
    lines = [line.rstrip("\n") for line in raw_lines]
    seen: dict[str, int] = {}
    groups: list[_GlossaryGroup] = []
    fence_marker: str | None = None
    for index, line in enumerate(lines):
        fence = _FENCE_RE.match(line.strip())
        if fence:
            if fence_marker is None:
                fence_marker = fence.group(1)[0] * 3
            elif line.strip().startswith(fence_marker):
                fence_marker = None
            continue
        match = None if fence_marker else _HEADING_RE.match(line)
        if not match:
            continue
        base = slugify(match.group(2))
        count = seen.get(base, 0)
        if base:
            seen[base] = count + 1
        if len(match.group(1)) == GLOSSARY_GROUP_LEVEL:
            excluded = index + 1 < len(lines) and lines[index + 1].strip() == EXCLUDE_MARKER
            groups.append(
                _GlossaryGroup(index + 1, match.group(2), base if count == 0 else f"{base}-{count}", excluded)
            )
    return groups


def _terms_and_groups(
    glossary: ServedDocument, group_headings: Sequence[_GlossaryGroup], context: LinkContext
) -> tuple[dict[str, HelpTerm], list[HelpGroup]]:
    """Return the terms of the glossary's served entries and the groups that hold them."""
    terms: dict[str, HelpTerm] = {}
    members: dict[str, list[str]] = {}
    for section in glossary.sections:
        where = f"{glossary.path}:{section.first_line}"
        if section.anchor_id is None:
            raise HelpGenerationError(f"{where}: the entry '{section.heading}' has no id line")
        owner = [group for group in group_headings if group.line < section.first_line][-1:]
        if not owner:
            raise HelpGenerationError(f"{where}: the entry '{section.heading}' is under no level-2 heading")
        lines = rewrite_links(section.lines, section.body_first_line, glossary.path, context)
        split = _split_entry(lines)
        if split is None:
            raise HelpGenerationError(f"{where}: the entry '{section.heading}' has no short definition")
        terms[section.anchor_id] = HelpTerm(
            name=section.heading, definition=split[0], body=split[1], group=owner[0].slug
        )
        members.setdefault(owner[0].slug, []).append(section.anchor_id)
    groups = [
        HelpGroup(id=group.slug, title=group.title, terms=tuple(members[group.slug]))
        for group in group_headings
        if group.slug in members
    ]
    return terms, groups


def _document(served: ServedDocument, context: LinkContext) -> HelpDocument:
    """Return the bundle document of one served guide: its title, introduction and sections below level 1."""
    titles = [section for section in served.sections if section.level == 1]
    if len(titles) != 1:
        raise HelpGenerationError(f"{served.path}: expected one level-1 heading, found {len(titles)}")
    sections: list[HelpSection] = []
    for section in served.sections:
        if section.level == 1:
            continue
        if not section.slug:
            raise HelpGenerationError(
                f"{served.path}:{section.first_line}: the heading '{section.heading}' has no slug"
            )
        lines = rewrite_links(section.lines, section.body_first_line, served.path, context)
        sections.append(
            HelpSection(id=section.slug, heading=section.heading, level=section.level, markdown=trim(lines))
        )
    introduction = rewrite_links(titles[0].lines, titles[0].body_first_line, served.path, context)
    return HelpDocument(title=titles[0].heading, introduction=trim(introduction), sections=tuple(sections))


def document_ids(documents: Sequence[ServedDocument]) -> dict[str, str]:
    """Return the bundle document id of each served guide: the fixed ids, and each strategy guide's alias."""
    strategy_ids = {f"{STRATEGY_GUIDE_DIRECTORY}/{guide_name(item)}.md": item.alias for item in STRATEGIES}
    ids: dict[str, str] = {}
    for served in documents:
        if served.path == USER_GLOSSARY:
            continue
        found = FIXED_DOCUMENT_IDS.get(served.path) or strategy_ids.get(served.path)
        if found is None:
            raise HelpGenerationError(f"{served.path}: the served document matches no document id")
        ids[served.path] = found
    return ids


def build_bundle(repo_root: Path = REPOSITORY_ROOT) -> HelpBundle:
    """Return the help bundle of the served documents of ``repo_root``, validated by ``HelpBundle``."""
    documents = served_documents(repo_root)
    ids = document_ids(documents)
    slugs = {
        served.path: next(section.slug for section in served.sections if section.level == 1)
        for served in documents
        if served.path in ids
    }
    context = LinkContext(ids, slugs)
    glossary = next((served for served in documents if served.path == USER_GLOSSARY), None)
    terms: dict[str, HelpTerm] = {}
    groups: list[HelpGroup] = []
    if glossary is not None:
        raw = (repo_root / USER_GLOSSARY).read_text(encoding="utf-8").splitlines()
        terms, groups = _terms_and_groups(glossary, _glossary_groups(raw), context)
    return HelpBundle(
        terms=terms,
        groups=tuple(groups),
        documents={ids[served.path]: _document(served, context) for served in documents if served.path in ids},
    )


def bundle_text(bundle: HelpBundle) -> str:
    """Return the canonical text of the bundle: sorted keys, two-space indent, trailing line feed."""
    return json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def help_gaps(path: Path = HELP_BUNDLE_FILE, repo_root: Path = REPOSITORY_ROOT) -> list[str]:
    """Return a message when the bundle file is missing or differs from the regenerated text."""
    if path.is_file() and path.read_bytes() == bundle_text(build_bundle(repo_root)).encode("utf-8"):
        return []
    return [f"help_bundle.json is missing or out of date; run {REGENERATE_COMMAND}"]


def write_help(path: Path = HELP_BUNDLE_FILE, repo_root: Path = REPOSITORY_ROOT) -> bool:
    """Write the bundle, returning whether the file changed."""
    data = bundle_text(build_bundle(repo_root)).encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def main(argv: Sequence[str] | None = None, *, path: Path = HELP_BUNDLE_FILE, repo_root: Path = REPOSITORY_ROOT) -> int:
    """Write the bundle to ``path``, or with ``--check`` report drift; return 1 on drift or on any refusal."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="Report a missing or out-of-date bundle; write nothing.")
    arguments = parser.parse_args(argv)
    problems = check_served_content(repo_root)
    if problems:
        sys.stderr.write("".join(f"{problem}\n" for problem in problems))
        sys.stderr.write(
            f"generate_help: {len(problems)} served-content problem(s); nothing was written or compared.\n"
        )
        return 1
    try:
        if arguments.check:
            gaps = help_gaps(path, repo_root)
            sys.stderr.write("".join(f"{gap}\n" for gap in gaps))
            return 1 if gaps else 0
        sys.stdout.write("wrote help_bundle.json\n" if write_help(path, repo_root) else "help_bundle.json is current\n")
    except (HelpGenerationError, ValueError) as error:
        sys.stderr.write(f"generate_help: {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
