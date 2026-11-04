"""The route table: every endpoint's method, path, parameters and response model for each status code.

The application and the OpenAPI generator both read this table, and a test checks that the application serves exactly
the routes it lists. A response model is a document type; a status with several models is any one of them.
"""

from dataclasses import dataclass
from typing import Any, Final, Literal

from pydantic import BaseModel

from investment_analysis_engine.api.documents import InfoDocument, ReplayTextDocument, StrategiesDocument
from investment_analysis_engine.reporting.documents.failure import FailureEnvelope
from investment_analysis_engine.strategy_wiring import STRATEGIES
from investment_analysis_engine.workspace_documents.runs import RunsListDocument
from investment_analysis_engine.workspace_documents.runs_compare import RunsCompareDocument
from investment_analysis_engine.workspace_documents.watchlist import WatchlistDocument, WatchlistListDocument

DEFAULT_RUNS_LIMIT: Final = 20
"""The page size of the runs list when ``limit`` is not given; the command line's default."""

DEFAULT_RUNS_OFFSET: Final = 0
"""The rows the runs list skips when ``offset`` is not given; the command line's default."""

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

    method: Literal["GET"]
    path: str
    operation_id: str
    summary: str
    parameters: tuple[ParameterSpec, ...]
    responses: tuple[tuple[int, tuple[type[BaseModel], ...]], ...]

    @property
    def query_names(self) -> frozenset[str]:
        """Return the names of the query parameters the endpoint accepts."""
        return frozenset(item.name for item in self.parameters if item.location == "query")


def _uuid_path(name: str, description: str) -> ParameterSpec:
    return ParameterSpec(name, "path", True, description, (("type", "string"), ("format", "uuid")))


def _query(name: str, description: str, *schema: tuple[str, Any], required: bool = False) -> ParameterSpec:
    return ParameterSpec(name, "query", required, description, (("type", "string"), *schema))


def _responses(
    success: tuple[type[BaseModel], ...], *, lookup: bool, database: bool
) -> tuple[tuple[int, tuple[type[BaseModel], ...]], ...]:
    """Return the responses of an endpoint by status: its success document and each failure status it can give.

    Every endpoint can answer 400 (the Host and Origin checks, or a rejected parameter), 401, 405 and 500; ``lookup``
    adds 404 for a missing resource and ``database`` adds 503 for a busy database.
    """
    failure = (FailureEnvelope,)
    statuses: list[tuple[int, tuple[type[BaseModel], ...]]] = [(200, success), (400, failure), (401, failure)]
    if lookup:
        statuses.append((404, failure))
    statuses.append((405, failure))
    statuses.append((500, failure))
    if database:
        statuses.append((503, failure))
    return tuple(sorted(statuses))


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
        _responses((WatchlistDocument,), lookup=True, database=True),
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
)
"""Every endpoint, in the order the documentation lists them."""


__all__ = [
    "DEFAULT_RUNS_LIMIT",
    "DEFAULT_RUNS_OFFSET",
    "ROUTES",
    "TEXT_MODES",
    "ParameterSpec",
    "RouteSpec",
]
