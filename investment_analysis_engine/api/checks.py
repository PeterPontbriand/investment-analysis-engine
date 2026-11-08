"""The checks every request passes before routing: Host, Origin, the preflight answer and the bearer token."""

import secrets
from collections.abc import Collection

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from investment_analysis_engine.api.origins import normalize_origin
from investment_analysis_engine.api.responses import failure_of
from investment_analysis_engine.api.routes import ROUTES
from investment_analysis_engine.core.failure_codes import FailureReasonCode

PREFLIGHT_MAX_AGE_SECONDS = 600
"""How long a browser may reuse a preflight answer."""

PREFLIGHT_ALLOWED_METHODS = ", ".join(dict.fromkeys(route.method for route in ROUTES))
"""The methods a preflight allows: exactly those the route table declares, in the order it first uses them."""

PREFLIGHT_ALLOWED_HEADERS = "Authorization, Content-Type, Accept-Language"
"""The request headers a preflight allows: the bearer token, the type of a body and the language wanted."""

_BEARER_PREFIX = "bearer "


class RequestChecks:
    """ASGI middleware that rejects a request before any route sees it.

    The checks run in a fixed order: the ``Host`` header, then the ``Origin`` header, then the answer to a preflight
    (an ``OPTIONS`` request from an allowed origin that carries ``Access-Control-Request-Method``), then the bearer
    token. A request that fails none of them is passed on.
    """

    def __init__(self, app: ASGIApp, *, token: str, port: int, allowed_origins: Collection[str]) -> None:
        """Keep the token, the exact ``Host`` values of the loopback binding and the normalized allowed origins."""
        self._app = app
        self._token = token.encode("utf-8")
        self._hosts = frozenset({f"127.0.0.1:{port}", f"localhost:{port}"})
        self._origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Check an HTTP request and pass it on, or answer it with a failure."""
        if scope["type"] == "lifespan":
            await self._app(scope, receive, send)
            return
        if scope["type"] != "http":
            await send({"type": "websocket.close"})
            return
        headers = Headers(scope=scope)
        if headers.get("host") not in self._hosts:
            response = failure_of(
                FailureReasonCode.HOST_NOT_ALLOWED,
                "The Host header must name this server's loopback address and port.",
            )
            await response(scope, receive, send)
            return
        origin = headers.get("origin")
        if origin is not None:
            canonical = normalize_origin(origin)
            if canonical is None or canonical not in self._origins:
                response = failure_of(
                    FailureReasonCode.ORIGIN_NOT_ALLOWED, "Requests from this origin are not allowed."
                )
                await response(scope, receive, send)
                return
        reply = send if origin is None else _with_cors_headers(send, origin)
        if origin is not None and scope["method"] == "OPTIONS" and "access-control-request-method" in headers:
            preflight = Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Methods": PREFLIGHT_ALLOWED_METHODS,
                    "Access-Control-Allow-Headers": PREFLIGHT_ALLOWED_HEADERS,
                    "Access-Control-Max-Age": str(PREFLIGHT_MAX_AGE_SECONDS),
                    "Cache-Control": "no-store",
                },
            )
            await preflight(scope, receive, reply)
            return
        if not self._token_matches(headers.get("authorization")):
            response = failure_of(
                FailureReasonCode.NOT_AUTHENTICATED,
                "A valid bearer token is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, reply)
            return
        await self._app(scope, receive, reply)

    def _token_matches(self, authorization: str | None) -> bool:
        """Return whether the ``Authorization`` header carries this launch's token as a bearer credential."""
        if authorization is None or not authorization.lower().startswith(_BEARER_PREFIX):
            return False
        presented = authorization[len(_BEARER_PREFIX) :].strip().encode("utf-8")
        return secrets.compare_digest(presented, self._token)


def _with_cors_headers(send: Send, origin: str) -> Send:
    """Wrap ``send`` so the response start carries the headers an allowed origin needs."""

    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = MutableHeaders(scope=message)
            headers["Access-Control-Allow-Origin"] = origin
            headers.append("Vary", "Origin")
            headers["Access-Control-Expose-Headers"] = "WWW-Authenticate"
        await send(message)

    return wrapped


__all__ = ["PREFLIGHT_ALLOWED_HEADERS", "PREFLIGHT_ALLOWED_METHODS", "PREFLIGHT_MAX_AGE_SECONDS", "RequestChecks"]
