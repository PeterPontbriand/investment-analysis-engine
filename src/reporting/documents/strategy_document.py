"""The header and tail every strategy ``--json`` document shares, declared once.

A strategy document is three parts: this module's header, the strategy's own body, and this module's tail. Each
strategy's ``envelope.py`` combines them as ``class Document(StrategyDocumentTail, Body, StrategyDocumentHeader[...])``.
Pydantic collects fields from the base-most class first, so listing the tail first and the header last in the bases
gives the order header, body, tail in the model, in the written JSON and in the generated schema. A new shared key
is added here, once, and every strategy document takes it; the conformance test fails for a document that does not.

The header's key order is part of the contract:

``schema_version``
    The document's own version.
``analysis``, ``method``
    Which strategy and method wrote it. They are generic, so each document's schema pins its own identifiers.
``ticker``
    The instrument.
``status``
    Whether the calculation ran, as :class:`~src.core.analysis_status.CalculationStatus`; never a verdict.
``requested_as_of``
    The point in time the user asked for; null means now.
``effective_as_of``
    The instant the analysis was evaluated at: ``requested_as_of`` when given, else the execution time.
``security_identity``, ``instrument_kind``
    The identity and instrument-kind evidence the run retained.

The tail is ``warnings``, ``limitations`` and ``diagnostics``, in that order.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from src.core.analysis_status import CalculationStatus
from src.reporting.documents.shared_parts import (
    DiagnosticEntry,
    DocumentPart,
    InstrumentKindPart,
    SecurityIdentityPart,
)
from src.reporting.documents.timestamp import DocumentTimestamp

HEADER_KEYS: tuple[str, ...] = (
    "schema_version",
    "analysis",
    "method",
    "ticker",
    "status",
    "requested_as_of",
    "effective_as_of",
    "security_identity",
    "instrument_kind",
)
"""The header's keys in document order; the conformance test checks the model against them."""

TAIL_KEYS: tuple[str, ...] = ("warnings", "limitations", "diagnostics")
"""The tail's keys in document order."""


class StrategyDocumentHeader[AnalysisIdT: str, MethodIdT: str](DocumentPart):
    """The keys every strategy document begins with."""

    schema_version: int
    analysis: AnalysisIdT
    method: MethodIdT
    ticker: str
    status: CalculationStatus
    requested_as_of: DocumentTimestamp | None
    effective_as_of: DocumentTimestamp
    security_identity: SecurityIdentityPart
    instrument_kind: InstrumentKindPart | None


class StrategyDocumentTail(DocumentPart):
    """The keys every strategy document ends with."""

    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    diagnostics: tuple[DiagnosticEntry, ...]


def strategy_document_json(document: BaseModel) -> str:
    """Return ``document`` as the text a strategy ``--json`` command writes.

    Keys are written in the model's field order, at every depth, so a document begins with the shared header and ends
    with the shared tail. The other documents (failure, workspace, database) keep sorted keys through
    :func:`~src.reporting.presentation.json_document`.
    """
    return json.dumps(document.model_dump(mode="json"), indent=2, ensure_ascii=False, allow_nan=False)


__all__ = [
    "HEADER_KEYS",
    "TAIL_KEYS",
    "StrategyDocumentHeader",
    "StrategyDocumentTail",
    "strategy_document_json",
]
