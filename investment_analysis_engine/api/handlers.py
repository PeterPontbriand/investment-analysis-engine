"""The endpoint handlers: each reads its parameters, calls one application operation and returns a document.

A handler is a plain function, so Starlette runs it in its thread pool; each operation opens its own database
connection, as every application operation does. Failures never escape a handler: they leave as failure envelopes.
"""

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

from investment_analysis_engine.api.documents import (
    build_info_document,
    build_replay_text_document,
    build_strategies_document,
)
from investment_analysis_engine.api.responses import document_response, failure_of, failure_response
from investment_analysis_engine.api.routes import (
    DEFAULT_RUNS_LIMIT,
    DEFAULT_RUNS_OFFSET,
    TEXT_MODES,
    RouteSpec,
)
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.runs import (
    RunQueryNames,
    build_run_query,
    compare_refresh_runs,
    declared_method_id,
    list_runs,
    replay_run_document,
    replay_run_text,
)
from investment_analysis_engine.application.watchlists import get_watchlist_by_id, list_watchlists
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_classification import classify_failure
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.reporting.failure_envelope import failure_envelope
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.workspace_documents.runs import build_runs_list_document
from investment_analysis_engine.workspace_documents.watchlist import (
    build_watchlist_document,
    build_watchlist_list_document,
)

logger = logging.getLogger(__name__)

UNEXPECTED_FAILURE_MESSAGE = "The request failed unexpectedly."
"""The one message of an unexpected failure; the detail goes to the log with its traceback."""

_RUN_QUERY_NAMES = RunQueryNames(
    ticker="ticker", method="method_id", status="status", refresh_id="refresh_id", limit="limit", offset="offset"
)
_TEXT_MODES: Mapping[str, TextPresentationMode] = {
    "concise": PresentationMode.CONCISE,
    "details": PresentationMode.DETAILS,
    "diagnostics": PresentationMode.DIAGNOSTICS,
}
_INTEGER = re.compile(r"-?[0-9]+")

type Endpoint = Callable[[Request], Response]


@dataclass(frozen=True)
class RequestParameters:
    """The checked parameters of one request: the path's, and the query's with each name given exactly once."""

    path: Mapping[str, str]
    query: Mapping[str, str]


type Operation = Callable[[ApplicationContext, RequestParameters], BaseModel]


def _uuid(parameters: RequestParameters, name: str) -> UUID:
    """Return the path parameter ``name`` as a UUID."""
    value = parameters.path[name]
    try:
        return UUID(value)
    except ValueError as exc:
        raise InvalidParameterError(f"{name} {value!r} is not a valid ID.", parameters=(name,)) from exc


def _integer(parameters: RequestParameters, name: str, default: int) -> int:
    """Return the query parameter ``name`` as an integer, or ``default`` when it is absent."""
    value = parameters.query.get(name)
    if value is None:
        return default
    if _INTEGER.fullmatch(value) is None:
        raise InvalidParameterError(f"{name} must be an integer.", parameters=(name,))
    return int(value)


def _query_values(request: Request, route: RouteSpec) -> Mapping[str, str]:
    """Return the query parameters, rejecting an unknown name and a name given more than once."""
    values: dict[str, str] = {}
    allowed = route.query_names
    for name, value in request.query_params.multi_items():
        label = name or "query"
        if name not in allowed:
            raise InvalidParameterError(f"{label} is not a parameter of this endpoint.", parameters=(label,))
        if name in values:
            raise InvalidParameterError(f"{name} must be given at most once.", parameters=(name,))
        values[name] = value
    return values


def error_response(exception: Exception) -> Response:
    """Return the failure response of an exception raised while serving a request.

    An exception that declares its own failure code keeps its message; any other is an ``execution_error`` with one
    fixed message, and its detail and traceback go to the log, so no library text reaches the client.
    """
    if isinstance(getattr(exception, "reason_code", None), FailureReasonCode):
        classification = classify_failure(exception)
        try:
            return failure_response(failure_envelope(classification.reason_code, str(exception), cause=exception))
        except ValueError:
            # The exception declares a code whose envelope needs facts the exception does not carry.
            logger.exception("A failure could not be described by its own code.")
            return failure_of(FailureReasonCode.EXECUTION_ERROR, UNEXPECTED_FAILURE_MESSAGE)
    logger.error("Unexpected failure while serving a request.", exc_info=exception)
    return failure_of(FailureReasonCode.EXECUTION_ERROR, UNEXPECTED_FAILURE_MESSAGE)


def endpoint_for(route: RouteSpec, operation: Operation, context: ApplicationContext) -> Endpoint:
    """Build the handler of ``route``: check its parameters, run ``operation`` and answer with its document."""

    def endpoint(request: Request) -> Response:
        try:
            parameters = RequestParameters(path=request.path_params, query=_query_values(request, route))
            return document_response(operation(context, parameters))
        except Exception as exc:
            return error_response(exc)

    return endpoint


def _info(settings: ProjectSettings) -> Operation:
    document = build_info_document(
        engine_version=ProjectSettings.version,
        sec_identity_configured=bool(settings.sec_user_agent and settings.sec_user_agent.strip()),
    )
    return lambda _context, _parameters: document


def _strategies(_context: ApplicationContext, _parameters: RequestParameters) -> BaseModel:
    return build_strategies_document()


def _watchlists(context: ApplicationContext, _parameters: RequestParameters) -> BaseModel:
    return build_watchlist_list_document(list_watchlists(context))


def _watchlist(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    return build_watchlist_document(get_watchlist_by_id(context, _uuid(parameters, "watchlist_id")))


def _runs(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    query = build_run_query(
        names=_RUN_QUERY_NAMES,
        resolve_method=lambda value: declared_method_id(value, name="method_id"),
        ticker=parameters.query.get("ticker"),
        method=parameters.query.get("method_id"),
        status=parameters.query.get("status"),
        refresh_id=parameters.query.get("refresh_id"),
        limit=_integer(parameters, "limit", DEFAULT_RUNS_LIMIT),
        offset=_integer(parameters, "offset", DEFAULT_RUNS_OFFSET),
    )
    page = list_runs(context, query)
    return build_runs_list_document(page.summaries, has_more=page.has_more)


def _run(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    return replay_run_document(context, _uuid(parameters, "analysis_run_id"))


def _run_text(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    run_id = _uuid(parameters, "analysis_run_id")
    value = parameters.query.get("mode")
    if value is None:
        raise InvalidParameterError("mode is required.", parameters=("mode",))
    mode = _TEXT_MODES.get(value)
    if mode is None:
        raise InvalidParameterError(f"mode must be one of: {', '.join(TEXT_MODES)}.", parameters=("mode",))
    return build_replay_text_document(mode, replay_run_text(context, run_id, mode))


def _compare(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    return compare_refresh_runs(context, _uuid(parameters, "refresh_id"))


def operations(settings: ProjectSettings) -> Mapping[str, Operation]:
    """Return the operation of each route in the table, keyed by the route's operation ID."""
    return {
        "get_info": _info(settings),
        "list_strategies": _strategies,
        "list_watchlists": _watchlists,
        "get_watchlist": _watchlist,
        "list_runs": _runs,
        "get_run": _run,
        "get_run_text": _run_text,
        "compare_refresh": _compare,
    }


__all__ = [
    "UNEXPECTED_FAILURE_MESSAGE",
    "Endpoint",
    "Operation",
    "RequestParameters",
    "endpoint_for",
    "error_response",
    "operations",
]
