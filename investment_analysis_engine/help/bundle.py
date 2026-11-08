"""The help bundle: the served glossary terms and guides, generated into ``help_bundle.json``.

``scripts/generate_help.py`` writes the bundle from the served Markdown documents and the drift check compares it.
:func:`load_help_bundle` reads the shipped file and validates it with :class:`HelpBundle`, whose validator checks that
the bundle holds together: every term is in exactly one group, every group lists existing terms, and every
``help:`` link in any text resolves.

Only term ids and document ids are stable references. Section ids and group ids are valid only within the bundle that
carries them.
"""

import re
from functools import cache
from importlib.resources import files

from pydantic import BaseModel, ConfigDict, Field, model_validator

HELP_BUNDLE_FILE_NAME = "help_bundle.json"
TERM_LINK_PREFIX = "help:terms/"
DOCUMENT_LINK_PREFIX = "help:documents/"

_HELP_LINK_RE = re.compile(r"\]\((help:[^)\s]*)")


class _Frozen(BaseModel):
    """The shared configuration: immutable, and no field beyond those declared."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class HelpTerm(_Frozen):
    """One glossary term.

    Attributes:
        name: The entry's heading.
        definition: The entry's first paragraph, its short definition.
        body: The rest of the entry, or an empty string when the entry is only a definition.
        group: The id of the group that lists this term.
    """

    name: str
    definition: str
    body: str
    group: str


class HelpGroup(_Frozen):
    """An ordered set of terms, following one section of the glossary.

    Attributes:
        id: The GitHub heading slug of the glossary section's heading; valid only within the bundle.
        title: The section's heading text.
        terms: The ids of the group's terms, in glossary order.
    """

    id: str
    title: str
    terms: tuple[str, ...]


class HelpSection(_Frozen):
    """One section of a served document.

    Attributes:
        id: The heading's GitHub slug, counted over the whole source file; valid only within the bundle.
        heading: The heading text.
        level: The heading level, from 2 to 6.
        markdown: The text under the heading, up to the next heading of any level.
    """

    id: str
    heading: str
    level: int = Field(ge=2, le=6)
    markdown: str


class HelpDocument(_Frozen):
    """One served guide.

    Attributes:
        title: The document's level-1 heading text.
        introduction: The text under the level-1 heading.
        sections: Every served heading below level 1, in file order.
    """

    title: str
    introduction: str
    sections: tuple[HelpSection, ...]


class HelpBundle(_Frozen):
    """The whole served help content: terms by id, their groups, and documents by id.

    Attributes:
        terms: The glossary terms, keyed by term id.
        groups: The glossary's sections, in file order.
        documents: The served guides, keyed by document id.
    """

    terms: dict[str, HelpTerm]
    groups: tuple[HelpGroup, ...]
    documents: dict[str, HelpDocument]

    @model_validator(mode="after")
    def _check_integrity(self) -> "HelpBundle":
        """Fail, naming the term, group, document or section and the bad id or link, unless the bundle is coherent."""
        problems = [*self._group_problems(), *self._link_problems()]
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _group_problems(self) -> list[str]:
        """Return what is wrong with the terms' groups and the groups' terms."""
        listed: dict[str, list[str]] = {}
        problems: list[str] = []
        for group in self.groups:
            for term_id in group.terms:
                listed.setdefault(term_id, []).append(group.id)
                if term_id not in self.terms:
                    problems.append(f"group {group.id!r} lists term {term_id!r}, which does not exist")
        for term_id, term in self.terms.items():
            owners = listed.get(term_id, [])
            if len(owners) != 1:
                problems.append(f"term {term_id!r} is in {len(owners)} groups; it must be in exactly one")
            elif term.group != owners[0]:
                problems.append(f"term {term_id!r} names group {term.group!r} but group {owners[0]!r} lists it")
        return problems

    def _link_problems(self) -> list[str]:
        """Return every ``help:`` link, in any text, that does not resolve."""
        problems: list[str] = []
        for term_id, term in self.terms.items():
            problems.extend(self._unresolved(f"term {term_id!r}", f"{term.definition}\n{term.body}"))
        for document_id, document in self.documents.items():
            problems.extend(self._unresolved(f"document {document_id!r} introduction", document.introduction))
            for section in document.sections:
                problems.extend(self._unresolved(f"document {document_id!r} section {section.id!r}", section.markdown))
        return problems

    def _unresolved(self, where: str, text: str) -> list[str]:
        """Return a message for each ``help:`` link in ``text`` that names nothing in the bundle."""
        return [
            f"{where} has the link {link!r}, which {reason}"
            for link in _HELP_LINK_RE.findall(text)
            if (reason := self._link_failure(link)) is not None
        ]

    def _link_failure(self, link: str) -> str | None:
        """Return why ``link`` resolves to nothing, or ``None`` when it resolves."""
        if link.startswith(TERM_LINK_PREFIX):
            term_id = link.removeprefix(TERM_LINK_PREFIX)
            return None if term_id in self.terms else f"names no term {term_id!r}"
        if link.startswith(DOCUMENT_LINK_PREFIX):
            document_id, _, section_id = link.removeprefix(DOCUMENT_LINK_PREFIX).partition("#")
            document = self.documents.get(document_id)
            if document is None:
                return f"names no document {document_id!r}"
            if "#" in link and section_id not in {section.id for section in document.sections}:
                return f"names no section {section_id!r} of document {document_id!r}"
            return None
        return "is neither a term link nor a document link"


@cache
def load_help_bundle() -> HelpBundle:
    """Return the shipped help bundle, read once and validated.

    A missing or invalid file raises as it is: ``FileNotFoundError`` or ``pydantic.ValidationError``.
    """
    text = files("investment_analysis_engine.help").joinpath(HELP_BUNDLE_FILE_NAME).read_text(encoding="utf-8")
    return HelpBundle.model_validate_json(text)
