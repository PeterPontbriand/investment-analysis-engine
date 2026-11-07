"""The endpoint handlers: each reads its parameters, calls one application operation and returns a document.

A handler is a plain function, so Starlette runs it in its thread pool; each operation opens its own database
connection, as every application operation does. Failures never escape a handler: they leave as failure envelopes.
"""

import logging
import re
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, JsonValue
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response

from investment_analysis_engine.api.documents import (
    AnalysisDocument,
    AnalysisTextDocument,
    build_info_document,
    build_replay_text_document,
    build_strategies_document,
    installed_engine_version,
)
from investment_analysis_engine.api.request_bodies import (
    AddEntriesRequest,
    AnalysisRequest,
    RemoveMethodRequest,
    RemoveTickersRequest,
    RequestBody,
    WatchlistNameRequest,
    read_body,
    read_json_object,
    read_request,
)
from investment_analysis_engine.api.responses import (
    DescribedFailure,
    document_response,
    failure_of,
    failure_response,
)
from investment_analysis_engine.api.routes import (
    DEFAULT_RUNS_LIMIT,
    DEFAULT_RUNS_OFFSET,
    TEXT_MODES,
    RouteSpec,
)
from investment_analysis_engine.api.selection_forms import build_selection_form_document
from investment_analysis_engine.application.analysis import analyze
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.failures import SavingFailureError, describe_failure
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.runs import (
    RunQueryNames,
    build_run_query,
    compare_refresh_runs,
    declared_method_id,
    list_runs,
    parse_refresh_id,
    replay_run_document,
    replay_run_text,
)
from investment_analysis_engine.application.selections import build_selection
from investment_analysis_engine.application.watchlists import (
    add_watchlist_entries,
    create_watchlist,
    delete_watchlist,
    get_watchlist_by_id,
    list_watchlists,
    remove_watchlist_entry,
    remove_watchlist_method,
    remove_watchlist_tickers,
    rename_watchlist,
)
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_classification import classify_failure
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.tickers import normalize_ticker
from investment_analysis_engine.reporting.failure_envelope import failure_envelope
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.workspace.strategy_types import SelectionMember
from investment_analysis_engine.workspace.watchlists import WatchlistId
from investment_analysis_engine.workspace_documents.runs import build_runs_list_document
from investment_analysis_engine.workspace_documents.watchlist import (
    build_delete_document,
    build_removal_document,
    build_rename_document,
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

type Endpoint = Callable[[Request], Response] | Callable[[Request], Awaitable[Response]]


@dataclass(frozen=True)
class RequestParameters:
    """The checked parameters of one request: the path's, the query's with each name given once, and the body."""

    path: Mapping[str, str]
    query: Mapping[str, str]
    request: RequestBody | None = None


type Operation = Callable[[ApplicationContext, RequestParameters], BaseModel]


def _uuid(parameters: RequestParameters, name: str, kind: str) -> UUID:
    """Return the path parameter ``name`` as a UUID; ``kind`` names the sort of ID in the message."""
    value = parameters.path[name]
    try:
        return UUID(value)
    except ValueError as exc:
        raise InvalidParameterError(f"{name} {value!r} is not a valid {kind} ID.", parameters=(name,)) from exc


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
    if isinstance(exception, DescribedFailure):
        return failure_response(failure_envelope(exception.code, exception.message, cause=exception.cause))
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


def _serve(
    route: RouteSpec,
    operation: Operation,
    context: ApplicationContext,
    request: Request,
    document: Mapping[str, object] | None,
) -> Response:
    """Check a request's parameters and body, run ``operation`` and answer with its document or its failure."""
    try:
        body = None if route.request is None or document is None else read_request(route.request, document)
        parameters = RequestParameters(path=request.path_params, query=_query_values(request, route), request=body)
        return document_response(operation(context, parameters), status=route.success_status)
    except Exception as exc:
        return error_response(exc)


def endpoint_for(route: RouteSpec, operation: Operation, context: ApplicationContext) -> Endpoint:
    """Build the handler of ``route``: check its parameters and body, run ``operation`` and answer with its document.

    The operation is synchronous and runs in the thread pool; a route that takes a body reads it first, which is the
    one asynchronous step.
    """
    if route.request is None:

        def endpoint(request: Request) -> Response:
            return _serve(route, operation, context, request, None)

        return endpoint

    async def body_endpoint(request: Request) -> Response:
        try:
            document = read_json_object(request.headers.get("content-type"), await read_body(request))
        except Exception as exc:
            return error_response(exc)
        return await run_in_threadpool(_serve, route, operation, context, request, document)

    return body_endpoint


def _info(settings: ProjectSettings) -> Operation:
    document = build_info_document(
        engine_version=installed_engine_version(),
        sec_identity_configured=bool(settings.sec_user_agent and settings.sec_user_agent.strip()),
    )
    return lambda _context, _parameters: document


def _strategies(_context: ApplicationContext, _parameters: RequestParameters) -> BaseModel:
    return build_strategies_document()


def _watchlists(context: ApplicationContext, _parameters: RequestParameters) -> BaseModel:
    return build_watchlist_list_document(list_watchlists(context))


def _watchlist(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    return build_watchlist_document(get_watchlist_by_id(context, _uuid(parameters, "watchlist_id", "watchlist")))


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
    return replay_run_document(context, _uuid(parameters, "analysis_run_id", "Analysis Run"))


def _run_text(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    run_id = _uuid(parameters, "analysis_run_id", "Analysis Run")
    value = parameters.query.get("mode")
    if value is None:
        raise InvalidParameterError("mode is required.", parameters=("mode",))
    mode = _TEXT_MODES.get(value)
    if mode is None:
        raise InvalidParameterError(f"mode must be one of: {', '.join(TEXT_MODES)}.", parameters=("mode",))
    return build_replay_text_document(mode, replay_run_text(context, run_id, mode))


def _compare(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    return compare_refresh_runs(context, parse_refresh_id(parameters.path["refresh_id"], name="refresh_id"))


def _body[BodyT: RequestBody](parameters: RequestParameters, model: type[BodyT]) -> BodyT:
    """Return the request body the route declared, which :func:`endpoint_for` has already checked."""
    body = parameters.request
    assert isinstance(body, model)  # the route table declares this model for the route
    return body


def _watchlist_ref(parameters: RequestParameters) -> WatchlistId:
    """Return the path's watchlist as the reference the actions take."""
    return WatchlistId(_uuid(parameters, "watchlist_id", "watchlist"))


@contextmanager
def _api_names(names: Mapping[str, str]) -> Iterator[None]:
    """Report an action's parameter error under the request's names for the action's parameters."""
    try:
        yield
    except ActionParameterError as exc:
        raise exc.named(names) from None


def _selection_names(error: ActionParameterError) -> dict[str, str]:
    """Return the request's name for each parameter a selection error names.

    A field of the selection is ``selection.<field>``; an undeclared method is the body's ``method_id``.
    """
    return {
        parameter: "method_id" if item.rule == "selection.undeclared_method" else f"selection.{parameter}"
        for item in error.errors
        for parameter in item.action_parameters
    }


def _selection(context: ApplicationContext, method_id: str, fields: Mapping[str, JsonValue]) -> SelectionMember:
    """Build the selection a request describes; its errors are named by their path in the request."""
    try:
        return build_selection(context, method_id, fields)
    except ActionParameterError as error:
        raise error.named(_selection_names(error)) from None


def _create(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    return build_watchlist_document(create_watchlist(context, _body(parameters, WatchlistNameRequest).name))


def _rename(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    ref = _watchlist_ref(parameters)
    name = _body(parameters, WatchlistNameRequest).name
    with _api_names({"new_name": "name"}):
        return build_rename_document(rename_watchlist(context, ref, name))


def _delete(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    return build_delete_document(delete_watchlist(context, _watchlist_ref(parameters)))


def _add_entries(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    ref = _watchlist_ref(parameters)
    body = _body(parameters, AddEntriesRequest)
    selection = _selection(context, body.method_id, body.selection)
    with _api_names({"entries": "tickers", "tickers": "tickers"}):
        return build_watchlist_document(
            add_watchlist_entries(context, ref, [(ticker, selection) for ticker in body.tickers])
        )


def _remove_entry(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    ref = _watchlist_ref(parameters)
    value = parameters.path["entry_number"]
    if _INTEGER.fullmatch(value) is None:
        raise InvalidParameterError("entry_number must be an integer.", parameters=("entry_number",))
    return build_removal_document(remove_watchlist_entry(context, ref, int(value)))


def _remove_tickers(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    ref = _watchlist_ref(parameters)
    return build_removal_document(
        remove_watchlist_tickers(context, ref, _body(parameters, RemoveTickersRequest).tickers)
    )


def _remove_method(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    ref = _watchlist_ref(parameters)
    return build_removal_document(
        remove_watchlist_method(context, ref, _body(parameters, RemoveMethodRequest).method_id)
    )


def _selection_form(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    return build_selection_form_document(context, parameters.path["method_id"])


def _analyze(context: ApplicationContext, parameters: RequestParameters) -> BaseModel:
    body = _body(parameters, AnalysisRequest)
    selection = _selection(context, body.method_id, body.selection)
    provider_check = context.settings.provider_check if body.provider_check is None else body.provider_check
    try:
        outcome = analyze(context, body.ticker, selection, save=body.save, provider_check=provider_check)
    except SavingFailureError as exc:
        # The analysis finished but its result could not be saved: describe it as the command line does, by ticker.
        description = describe_failure(exc.cause, normalize_ticker(body.ticker), saving=True)
        raise DescribedFailure(description.code, description.message, exc.cause) from exc
    return AnalysisDocument(
        analysis_run_id=outcome.analysis_run_id,
        document=outcome.document,
        text=AnalysisTextDocument(
            concise=outcome.render_text(PresentationMode.CONCISE),
            details=outcome.render_text(PresentationMode.DETAILS),
            diagnostics=outcome.render_text(PresentationMode.DIAGNOSTICS),
        ),
    )


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
        "get_selection_form": _selection_form,
        "create_watchlist": _create,
        "rename_watchlist": _rename,
        "delete_watchlist": _delete,
        "add_watchlist_entries": _add_entries,
        "remove_watchlist_entry": _remove_entry,
        "remove_watchlist_tickers": _remove_tickers,
        "remove_watchlist_method": _remove_method,
        "analyze": _analyze,
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
