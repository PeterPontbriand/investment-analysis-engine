"""The application factory: the route table, the request checks and the error answers, assembled."""

from collections.abc import Collection

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from investment_analysis_engine.api.checks import RequestChecks
from investment_analysis_engine.api.handlers import (
    Endpoint,
    RefreshJobsOfServer,
    endpoint_for,
    error_response,
    operations,
)
from investment_analysis_engine.api.locale_negotiation import LocaleNegotiation, add_locale_headers, negotiate_locale
from investment_analysis_engine.api.refresh_documents import event_recorder
from investment_analysis_engine.api.responses import failure_of
from investment_analysis_engine.api.routes import ROUTES, RouteSpec
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.refresh_jobs import RefreshJobs
from investment_analysis_engine.core.failure_codes import FailureReasonCode

ENDPOINT_NOT_FOUND_MESSAGE = "No such endpoint, or the endpoint does not accept this method."
"""The message of a request to a path or method the API does not serve."""


def _not_found(_request: Request, exception: Exception) -> Response:
    """Answer an unrouted request, 404 or 405 as the router decided, with the failure envelope."""
    status = exception.status_code if isinstance(exception, HTTPException) else 404
    headers = dict(exception.headers) if isinstance(exception, HTTPException) and exception.headers else None
    return failure_of(FailureReasonCode.ENDPOINT_NOT_FOUND, ENDPOINT_NOT_FOUND_MESSAGE, status=status, headers=headers)


def _unexpected(request: Request, exception: Exception) -> Response:
    """Answer an exception raised outside an endpoint handler with the fixed-message ``execution_error``.

    The server-error layer sends this answer outside the locale middleware, so it states the locale itself.
    """
    response = error_response(exception)
    add_locale_headers(response.headers, negotiate_locale(request.headers.get("accept-language")))
    return response


def _route(route: RouteSpec, endpoint: Endpoint) -> Route:
    """Build the route serving exactly the method the table declares, without the HEAD that Starlette adds to GET."""
    served = Route(route.path, endpoint, methods=[route.method])
    served.methods = {route.method}
    return served


def create_app(
    *, context: ApplicationContext, token: str, port: int, allowed_origins: Collection[str] = ()
) -> Starlette:
    """Build the API application.

    Args:
        context: What every operation needs from its caller, read once at launch.
        token: The bearer token every request must present.
        port: The port the server listens on, which the ``Host`` check names.
        allowed_origins: The origins, normalized by :func:`~investment_analysis_engine.api.origins.normalize_origin`,
            whose browsers may call the API; empty by default.

    Returns:
        The ASGI application. It serves exactly the routes of the route table, and keeps one latest refresh job.
    """
    refresh_jobs: RefreshJobsOfServer = RefreshJobs(event_recorder())
    handlers = operations(context.settings, refresh_jobs)
    app = Starlette(
        routes=[_route(route, endpoint_for(route, handlers[route.operation_id], context)) for route in ROUTES],
        middleware=[
            Middleware(LocaleNegotiation),
            Middleware(RequestChecks, token=token, port=port, allowed_origins=tuple(allowed_origins)),
        ],
        exception_handlers={HTTPException: _not_found, Exception: _unexpected},
    )
    app.router.redirect_slashes = False
    app.state.refresh_jobs = refresh_jobs
    return app


def refresh_jobs_of(app: Starlette) -> RefreshJobsOfServer:
    """Return the latest refresh job holder of a server built by :func:`create_app`."""
    jobs = app.state.refresh_jobs
    assert isinstance(jobs, RefreshJobs)  # create_app sets it
    return jobs


__all__ = ["ENDPOINT_NOT_FOUND_MESSAGE", "create_app", "refresh_jobs_of"]
