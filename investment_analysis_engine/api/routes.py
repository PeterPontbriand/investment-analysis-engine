"""The route table: every endpoint's method, path, parameters, request body and response model for each status code.

The application and the OpenAPI generator both read this table, and a test checks that the application serves exactly
the routes it lists. A response model is a document type; a status with several models is any one of them.
"""

from dataclasses import dataclass
from typing import Any, Final, Literal

from pydantic import BaseModel

from investment_analysis_engine.api.documents import (
    AnalysisDocument,
    InfoDocument,
    ReplayTextDocument,
    StrategiesDocument,
)
from investment_analysis_engine.api.refresh_documents import RefreshJobDocument
from investment_analysis_engine.api.request_bodies import (
    AddEntriesRequest,
    AnalysisRequest,
    RefreshRequest,
    RemoveMethodRequest,
    RemoveTickersRequest,
    RequestBody,
    WatchlistNameRequest,
)
from investment_analysis_engine.api.selection_forms import SelectionFormDocument
from investment_analysis_engine.reporting.documents.failure import FailureEnvelope
from investment_analysis_engine.strategy_wiring import STRATEGIES
from investment_analysis_engine.workspace_documents.runs import RunsListDocument
from investment_analysis_engine.workspace_documents.runs_compare import RunsCompareDocument
from investment_analysis_engine.workspace_documents.watchlist import (
    WatchlistDeleteDocument,
    WatchlistDocument,
    WatchlistListDocument,
    WatchlistRemovalDocument,
    WatchlistRenameDocument,
)

DEFAULT_RUNS_LIMIT: Final = 20
"""The page size of the runs list when ``limit`` is not given; the command line's default."""

DEFAULT_RUNS_OFFSET: Final = 0
"""The rows the runs list skips when ``offset`` is not given; the command line's default."""

DEFAULT_AFTER: Final = 0
"""The event sequence a refresh job poll starts after when ``after`` is not given: every event."""

SUCCESS_STATUS_LIMIT: Final = 300
"""The first status that is not a success."""

LOCATION_FIELDS: Final = ("refresh_id",)
"""The document fields a ``Location`` template may name."""

TEXT_MODES: Final = ("concise", "details", "diagnostics")
"""The values of the replay text endpoint's ``mode`` parameter."""


@dataclass(frozen=True)
class ParameterSpec:
    """One path or query parameter of an endpoint."""

    name: str
    location: Literal["path", "query"]
    required: bool
    description: str
    schema: tuple[tuple[str, Any], ...]

    def schema_dict(self) -> dict[str, Any]:
        """Return the parameter's JSON Schema fragment."""
        return dict(self.schema)


@dataclass(frozen=True)
class RouteSpec:
    """One endpoint: how it is called and every response it can give."""

    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str
    operation_id: str
    summary: str
    parameters: tuple[ParameterSpec, ...]
    responses: tuple[tuple[int, tuple[type[BaseModel], ...]], ...]
    request: type[RequestBody] | None = None
    location: str | None = None

    def location_of(self, document: BaseModel) -> str | None:
        """Return the ``Location`` header of the success response, or ``None`` for a route that has none.

        ``location`` is a path template whose placeholders name fields of the response document.
        """
        if self.location is None:
            return None
        return self.location.format(**{name: getattr(document, name) for name in LOCATION_FIELDS})

    @property
    def success_status(self) -> int:
        """Return the status of the endpoint's success response: the one below 300."""
        return next(status for status, _models in self.responses if status < SUCCESS_STATUS_LIMIT)

    @property
    def query_names(self) -> frozenset[str]:
        """Return the names of the query parameters the endpoint accepts."""
        return frozenset(item.name for item in self.parameters if item.location == "query")


def _uuid_path(name: str, description: str) -> ParameterSpec:
    return ParameterSpec(name, "path", True, description, (("type", "string"), ("format", "uuid")))


def _after(description: str) -> ParameterSpec:
    return ParameterSpec("after", "query", False, description, (("type", "string"), ("pattern", "^-?[0-9]+$")))


def _query(name: str, description: str, *schema: tuple[str, Any], required: bool = False) -> ParameterSpec:
    return ParameterSpec(name, "query", required, description, (("type", "string"), *schema))


def _responses(  # noqa: PLR0913
    success: tuple[type[BaseModel], ...],
    *,
    lookup: bool,
    database: bool,
    status: int = 200,
    conflict: bool = False,
) -> tuple[tuple[int, tuple[type[BaseModel], ...]], ...]:
    """Return the responses of an endpoint by status: its success document and each failure status it can give.

    Every endpoint can answer 400 (the Host and Origin checks, or a rejected parameter), 401, 405 and 500; ``lookup``
    adds 404 for a missing resource, ``conflict`` adds 409 for a change the stored data refuses and ``database`` adds
    503 for a busy database. ``status`` is the success status.
    """
    failure = (FailureEnvelope,)
    statuses: list[tuple[int, tuple[type[BaseModel], ...]]] = [(status, success), (400, failure), (401, failure)]
    if lookup:
        statuses.append((404, failure))
    if conflict:
        statuses.append((409, failure))
    statuses.append((405, failure))
    statuses.append((500, failure))
    if database:
        statuses.append((503, failure))
    return tuple(sorted(statuses))


def _method_path(description: str) -> ParameterSpec:
    return ParameterSpec(
        "method_id",
        "path",
        True,
        description,
        (("type", "string"), ("enum", [item.method_id for item in STRATEGIES])),
    )


ROUTES: Final[tuple[RouteSpec, ...]] = (
    RouteSpec(
        "GET",
        "/v1/info",
        "get_info",
        "Describe the engine this server runs.",
        (),
        _responses((InfoDocument,), lookup=False, database=False),
    ),
    RouteSpec(
        "GET",
        "/v1/strategies",
        "list_strategies",
        "List the strategies this engine supports.",
        (),
        _responses((StrategiesDocument,), lookup=False, database=False),
    ),
    RouteSpec(
        "GET",
        "/v1/watchlists",
        "list_watchlists",
        "List every watchlist.",
        (),
        _responses((WatchlistListDocument,), lookup=False, database=True),
    ),
    RouteSpec(
        "GET",
        "/v1/watchlists/{watchlist_id}",
        "get_watchlist",
        "Show one watchlist.",
        (_uuid_path("watchlist_id", "The watchlist's ID."),),
        _responses((WatchlistDocument,), lookup=True, database=True, conflict=True),
    ),
    RouteSpec(
        "GET",
        "/v1/runs",
        "list_runs",
        "List saved Analysis Runs, most recently completed first.",
        (
            _query("ticker", "Only runs of this ticker."),
            _query("method_id", "Only runs of this method."),
            _query("status", "Only runs with this outcome."),
            _query("refresh_id", "Only runs saved by this refresh.", ("format", "uuid")),
            _query(
                "limit",
                f"Maximum rows (1 to 100); {DEFAULT_RUNS_LIMIT} when absent.",
                ("pattern", "^-?[0-9]+$"),
            ),
            _query("offset", f"Rows to skip; {DEFAULT_RUNS_OFFSET} when absent.", ("pattern", "^-?[0-9]+$")),
        ),
        _responses((RunsListDocument,), lookup=False, database=True),
    ),
    RouteSpec(
        "GET",
        "/v1/runs/{analysis_run_id}",
        "get_run",
        "Show one saved run as its strategy's document.",
        (_uuid_path("analysis_run_id", "The run's ID."),),
        _responses(tuple(item.json_envelope for item in STRATEGIES), lookup=True, database=True),
    ),
    RouteSpec(
        "GET",
        "/v1/runs/{analysis_run_id}/text",
        "get_run_text",
        "Show one saved run as text in one presentation mode.",
        (
            _uuid_path("analysis_run_id", "The run's ID."),
            _query("mode", "The presentation mode.", ("enum", list(TEXT_MODES)), required=True),
        ),
        _responses((ReplayTextDocument,), lookup=True, database=True),
    ),
    RouteSpec(
        "GET",
        "/v1/refreshes/{refresh_id}/compare",
        "compare_refresh",
        "Compare the runs of one refresh: one row per ticker, one column group per strategy.",
        (_uuid_path("refresh_id", "The refresh's ID."),),
        _responses((RunsCompareDocument,), lookup=True, database=True),
    ),
    RouteSpec(
        "GET",
        "/v1/strategies/{method_id}/selection",
        "get_selection_form",
        "Describe the selection fields of one strategy, with their configured values.",
        (_method_path("The strategy's method identifier."),),
        _responses((SelectionFormDocument,), lookup=False, database=False),
    ),
    RouteSpec(
        "POST",
        "/v1/watchlists",
        "create_watchlist",
        "Create an empty watchlist.",
        (),
        _responses((WatchlistDocument,), lookup=False, database=True, status=201, conflict=True),
        WatchlistNameRequest,
    ),
    RouteSpec(
        "PATCH",
        "/v1/watchlists/{watchlist_id}",
        "rename_watchlist",
        "Rename a watchlist. Saved runs keep the name it had when they ran.",
        (_uuid_path("watchlist_id", "The watchlist's ID."),),
        _responses((WatchlistRenameDocument,), lookup=True, database=True, conflict=True),
        WatchlistNameRequest,
    ),
    RouteSpec(
        "DELETE",
        "/v1/watchlists/{watchlist_id}",
        "delete_watchlist",
        "Delete a watchlist and its entries. Saved runs are kept.",
        (_uuid_path("watchlist_id", "The watchlist's ID."),),
        _responses((WatchlistDeleteDocument,), lookup=True, database=True),
    ),
    RouteSpec(
        "POST",
        "/v1/watchlists/{watchlist_id}/entries",
        "add_watchlist_entries",
        "Add one entry per ticker for one strategy's selection.",
        (_uuid_path("watchlist_id", "The watchlist's ID."),),
        _responses((WatchlistDocument,), lookup=True, database=True, conflict=True),
        AddEntriesRequest,
    ),
    RouteSpec(
        "DELETE",
        "/v1/watchlists/{watchlist_id}/entries/{entry_number}",
        "remove_watchlist_entry",
        "Remove one entry by its 1-based number.",
        (
            _uuid_path("watchlist_id", "The watchlist's ID."),
            ParameterSpec(
                "entry_number",
                "path",
                True,
                "The entry's 1-based number, as the watchlist document shows it.",
                (("type", "string"), ("pattern", "^-?[0-9]+$")),
            ),
        ),
        _responses((WatchlistRemovalDocument,), lookup=True, database=True),
    ),
    RouteSpec(
        "POST",
        "/v1/watchlists/{watchlist_id}/remove-tickers",
        "remove_watchlist_tickers",
        "Remove every entry for the given tickers.",
        (_uuid_path("watchlist_id", "The watchlist's ID."),),
        _responses((WatchlistRemovalDocument,), lookup=True, database=True),
        RemoveTickersRequest,
    ),
    RouteSpec(
        "POST",
        "/v1/watchlists/{watchlist_id}/remove-method",
        "remove_watchlist_method",
        "Remove every entry of one strategy.",
        (_uuid_path("watchlist_id", "The watchlist's ID."),),
        _responses((WatchlistRemovalDocument,), lookup=True, database=True),
        RemoveMethodRequest,
    ),
    RouteSpec(
        "POST",
        "/v1/analyses",
        "analyze",
        "Analyze one ticker under one selection, and keep the result when asked.",
        (),
        _responses((AnalysisDocument,), lookup=False, database=True),
        AnalysisRequest,
    ),
    RouteSpec(
        "POST",
        "/v1/refreshes",
        "start_refresh",
        "Start a refresh job over a watchlist or a list of entries; one runs at a time. Answers 202 at once.",
        (),
        _responses((RefreshJobDocument,), lookup=True, database=True, status=202, conflict=True),
        RefreshRequest,
        location="/v1/refreshes/{refresh_id}/job",
    ),
    RouteSpec(
        "GET",
        "/v1/refreshes/job",
        "get_latest_refresh_job",
        "Show this server's latest refresh job, with its events after the sequence given.",
        (_after(f"The last event sequence already seen, from 0; {DEFAULT_AFTER} when absent."),),
        _responses((RefreshJobDocument,), lookup=True, database=False),
    ),
    RouteSpec(
        "GET",
        "/v1/refreshes/{refresh_id}/job",
        "get_refresh_job",
        "Show a refresh job, with its events after the sequence given.",
        (
            _uuid_path("refresh_id", "The refresh's ID."),
            _after(f"The last event sequence already seen, from 0; {DEFAULT_AFTER} when absent."),
        ),
        _responses((RefreshJobDocument,), lookup=True, database=False),
    ),
    RouteSpec(
        "POST",
        "/v1/refreshes/{refresh_id}/job/stop",
        "stop_refresh_job",
        "Stop a refresh job from starting more jobs; the ones running finish. Idempotent.",
        (_uuid_path("refresh_id", "The refresh's ID."),),
        _responses((RefreshJobDocument,), lookup=True, database=False),
    ),
)
"""Every endpoint, in the order the documentation lists them."""


__all__ = [
    "DEFAULT_AFTER",
    "DEFAULT_RUNS_LIMIT",
    "DEFAULT_RUNS_OFFSET",
    "LOCATION_FIELDS",
    "ROUTES",
    "TEXT_MODES",
    "ParameterSpec",
    "SUCCESS_STATUS_LIMIT",
    "RouteSpec",
]
