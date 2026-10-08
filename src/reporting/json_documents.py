"""The table of ``--json`` documents that no single strategy owns, and the commands that write each.

Every command that offers ``--json`` writes one typed document on success and a ``FailureEnvelope`` on failure.
This table lists the failure, workspace and database documents with their published schema file and the commands
that write them. The four strategy commands and ``runs show`` write strategy documents; each strategy's model is
its descriptor's ``json_envelope``, which this generic module cannot import, so the schema generator and the
conformance tests add them from the composition root.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel

from src.reporting.documents.database import DatabaseMaintenanceReport
from src.reporting.documents.failure import FailureEnvelope
from src.reporting.documents.refresh import RefreshSummaryDocument
from src.reporting.documents.runs import RunsListDocument
from src.reporting.documents.watchlist import WatchlistDeleteDocument, WatchlistDocument


@dataclass(frozen=True)
class JsonDocument:
    """One published document: its schema file, its typed model and the commands that write it on success."""

    schema_file: str
    model: type[BaseModel]
    commands: tuple[str, ...]


FAILURE_DOCUMENT: Final = JsonDocument("failure.schema.json", FailureEnvelope, ())
"""The document every ``--json`` command writes on failure; it names no command because all of them write it."""

DOCUMENTS: Final = (
    FAILURE_DOCUMENT,
    JsonDocument("database-maintenance-report.schema.json", DatabaseMaintenanceReport, ("db status", "db upgrade")),
    JsonDocument("watchlist.schema.json", WatchlistDocument, ("watchlist show", "watchlist rename")),
    JsonDocument("watchlist-delete.schema.json", WatchlistDeleteDocument, ("watchlist delete",)),
    JsonDocument("runs-list.schema.json", RunsListDocument, ("runs list",)),
    JsonDocument("refresh-summary.schema.json", RefreshSummaryDocument, ("refresh",)),
)
"""Every document this module lists, in the order the schemas are published."""

JSON_DOCUMENTS: Final = MappingProxyType({command: document for document in DOCUMENTS for command in document.commands})
"""The document each listed command writes on success, keyed by the command's space-separated path."""

STRATEGY_REPLAY_COMMANDS: Final = ("runs show",)
"""The commands that write a stored run's own strategy document, whichever strategy the run belongs to."""

__all__ = ["DOCUMENTS", "FAILURE_DOCUMENT", "JSON_DOCUMENTS", "STRATEGY_REPLAY_COMMANDS", "JsonDocument"]
