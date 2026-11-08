"""The help documents: the index, one term, one guide, and the term of every value of every code set.

Markdown is served as written, so a ``help:`` link stays a ``help:`` link for the client to follow. No document carries
a locale; the locale is stated in the ``Content-Language`` header.
"""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from investment_analysis_engine.api.term_references import code_terms_by_component
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.help.bundle import HelpBundle
from investment_analysis_engine.strategy_wiring import STRATEGIES


class _Document(BaseModel):
    """The shared configuration of a help document: immutable, and no field beyond those declared."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class HelpTermItem(_Document):
    """One term in the index: enough to show a list and a popup."""

    id: str = Field(description="The term's stable ID.")
    name: str = Field(description="The term's name, the heading of its entry.")
    definition: str = Field(description="The term's short definition, which depends on no link.")


class HelpGroupItem(_Document):
    """One group of the index: a section of the glossary and its terms."""

    id: str = Field(description="The group's ID, valid only within this bundle; it is not a stable reference.")
    title: str = Field(description="The group's title.")
    terms: tuple[HelpTermItem, ...] = Field(description="The group's terms, in glossary order.")


class HelpDocumentItem(_Document):
    """One guide in the index."""

    id: str = Field(description="The guide's stable ID.")
    title: str = Field(description="The guide's title.")


class HelpIndexDocument(_Document):
    """Everything the help offers, in the bundle's order: the glossary groups with their terms, and the guides."""

    schema_version: Literal[1] = Field(default=1, description="The version of this document's shape.")
    groups: tuple[HelpGroupItem, ...] = Field(description="The glossary's groups, in bundle order.")
    documents: tuple[HelpDocumentItem, ...] = Field(description="The guides, in bundle order.")


class HelpGroupReference(_Document):
    """The group that lists a term."""

    id: str = Field(description="The group's ID, valid only within this bundle; it is not a stable reference.")
    title: str = Field(description="The group's title.")


class HelpTermDocument(_Document):
    """One glossary term with its full entry."""

    schema_version: Literal[1] = Field(default=1, description="The version of this document's shape.")
    id: str = Field(description="The term's stable ID.")
    name: str = Field(description="The term's name, the heading of its entry.")
    definition: str = Field(description="The term's short definition, which depends on no link.")
    body: str = Field(description="The rest of the entry as Markdown; empty when the entry is only a definition.")
    group: HelpGroupReference = Field(description="The group that lists the term.")


class HelpSectionItem(_Document):
    """One section of a guide."""

    id: str = Field(description="The section's ID, valid only within this bundle; it is not a stable reference.")
    heading: str = Field(description="The section's heading text.")
    level: int = Field(description="The heading level, from 2 to 6.")
    markdown: str = Field(description="The text under the heading as Markdown, up to the next heading of any level.")


class HelpDocumentDocument(_Document):
    """One guide with its sections."""

    schema_version: Literal[1] = Field(default=1, description="The version of this document's shape.")
    id: str = Field(description="The guide's stable ID.")
    title: str = Field(description="The guide's title.")
    introduction: str = Field(description="The text under the guide's title as Markdown.")
    sections: tuple[HelpSectionItem, ...] = Field(description="The guide's sections, in file order.")


class HelpReferencesDocument(_Document):
    """The glossary term that explains each value of each code set the API returns."""

    schema_version: Literal[1] = Field(default=1, description="The version of this document's shape.")
    code_sets: dict[str, dict[str, str]] = Field(
        description="For each code set, named by its OpenAPI component, a map from each of its values to a term ID."
    )


class HelpTermNotFoundError(ValueError):
    """No help term has the ID asked for."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.HELP_TERM_NOT_FOUND


class HelpDocumentNotFoundError(ValueError):
    """No help document has the ID asked for."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.HELP_DOCUMENT_NOT_FOUND


HELP_TERM_NOT_FOUND_MESSAGE = "No help term has this ID."
"""The message of a request for a term the bundle lacks."""

HELP_DOCUMENT_NOT_FOUND_MESSAGE = "No help document has this ID."
"""The message of a request for a document the bundle lacks."""


def build_help_index_document(bundle: HelpBundle) -> HelpIndexDocument:
    """Build the index of a bundle: its groups with their terms, and its documents, in the bundle's order."""
    return HelpIndexDocument(
        groups=tuple(
            HelpGroupItem(
                id=group.id,
                title=group.title,
                terms=tuple(
                    HelpTermItem(
                        id=term_id, name=bundle.terms[term_id].name, definition=bundle.terms[term_id].definition
                    )
                    for term_id in group.terms
                ),
            )
            for group in bundle.groups
        ),
        documents=tuple(HelpDocumentItem(id=key, title=item.title) for key, item in bundle.documents.items()),
    )


def build_help_term_document(bundle: HelpBundle, term_id: str) -> HelpTermDocument:
    """Build the document of one term.

    Raises:
        HelpTermNotFoundError: If the bundle holds no term with this ID.
    """
    term = bundle.terms.get(term_id)
    if term is None:
        raise HelpTermNotFoundError(HELP_TERM_NOT_FOUND_MESSAGE)
    group = next(item for item in bundle.groups if item.id == term.group)  # the bundle's integrity check guarantees it
    return HelpTermDocument(
        id=term_id,
        name=term.name,
        definition=term.definition,
        body=term.body,
        group=HelpGroupReference(id=group.id, title=group.title),
    )


def build_help_document_document(bundle: HelpBundle, document_id: str) -> HelpDocumentDocument:
    """Build the document of one guide.

    Raises:
        HelpDocumentNotFoundError: If the bundle holds no document with this ID.
    """
    document = bundle.documents.get(document_id)
    if document is None:
        raise HelpDocumentNotFoundError(HELP_DOCUMENT_NOT_FOUND_MESSAGE)
    return HelpDocumentDocument(
        id=document_id,
        title=document.title,
        introduction=document.introduction,
        sections=tuple(
            HelpSectionItem(id=item.id, heading=item.heading, level=item.level, markdown=item.markdown)
            for item in document.sections
        ),
    )


def build_help_references_document() -> HelpReferencesDocument:
    """Build the references document from the shared registry and every declared strategy's own code sets.

    Raises:
        ValueError: If two tables are named for the same component.
    """
    return HelpReferencesDocument(code_sets=code_terms_by_component(STRATEGIES))


__all__ = [
    "HELP_DOCUMENT_NOT_FOUND_MESSAGE",
    "HELP_TERM_NOT_FOUND_MESSAGE",
    "HelpDocumentDocument",
    "HelpDocumentItem",
    "HelpDocumentNotFoundError",
    "HelpGroupItem",
    "HelpGroupReference",
    "HelpIndexDocument",
    "HelpReferencesDocument",
    "HelpSectionItem",
    "HelpTermDocument",
    "HelpTermItem",
    "HelpTermNotFoundError",
    "build_help_document_document",
    "build_help_index_document",
    "build_help_references_document",
    "build_help_term_document",
]
