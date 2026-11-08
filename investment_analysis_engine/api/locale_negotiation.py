"""Locale negotiation: the locale a request's ``Accept-Language`` header chooses, and the headers that state it.

:func:`negotiate_locale` is a pure function of the header text. :class:`LocaleNegotiation` is the outermost ASGI
middleware: it stores the chosen tag in the request's state and adds ``Content-Language`` and ``Vary: Accept-Language``
to every response the server sends. Negotiation never fails and never answers 406: a header that names no available
locale chooses the default.
"""

import re
from typing import Final

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from investment_analysis_engine.help.locales import DEFAULT_LOCALE, LOCALES

LOCALE_STATE_KEY: Final = "locale"
"""The key of the request state under which the chosen tag is stored."""

_TAG = re.compile(r"[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*")
_QUALITY = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_DECLARED: Final = frozenset(item.tag for item in LOCALES)


def _quality(parameter: str) -> float | None:
    """Return the q-value a parameter such as ``q=0.5`` states, or ``None`` when it is not one or is out of range."""
    name, separator, value = parameter.partition("=")
    value = value.strip()
    if not separator or name.strip().lower() != "q" or _QUALITY.fullmatch(value) is None:
        return None
    quality = float(value)
    return quality if 0.0 <= quality <= 1.0 else None


def _ranges(header: str) -> list[tuple[str, float]]:
    """Return the valid language ranges of a header, lowercase and with q > 0, in descending q and then header order."""
    ranges: list[tuple[str, float]] = []
    for item in header.split(","):
        tag, *parameters = (part.strip() for part in item.split(";"))
        if tag != "*" and _TAG.fullmatch(tag) is None:
            continue
        if len(parameters) > 1:
            continue
        quality = 1.0 if not parameters else _quality(parameters[0])
        if quality is None or quality == 0.0:
            continue
        ranges.append((tag.lower(), quality))
    return sorted(ranges, key=lambda item: -item[1])


def _available(tag: str) -> str | None:
    """Return the declared tag a range matches by dropping one subtag at a time, or ``None``."""
    parts = tag.split("-")
    while parts:
        candidate = "-".join(parts)
        if candidate in _DECLARED:
            return candidate
        parts.pop()
    return None


def negotiate_locale(header: str | None) -> str:
    """Return the tag of the available locale an ``Accept-Language`` header chooses.

    Tags match case-insensitively and by truncation (``en-Latn-CA`` matches ``en-Latn``, then ``en``). A q-value orders
    the ranges and ``q=0`` excludes one; equal q-values keep header order. An item with a malformed tag or q-value is
    skipped. ``*``, an absent header, a header with no valid item and a header that names no available locale choose
    the default locale.
    """
    if header is None:
        return DEFAULT_LOCALE
    for tag, _quality_value in _ranges(header):
        if tag == "*":
            return DEFAULT_LOCALE
        matched = _available(tag)
        if matched is not None:
            return matched
    return DEFAULT_LOCALE


def locale_of(request: Request) -> str:
    """Return the locale :class:`LocaleNegotiation` chose for a request, or the default when it did not run."""
    chosen = request.scope.get("state", {}).get(LOCALE_STATE_KEY)
    return chosen if isinstance(chosen, str) else DEFAULT_LOCALE


def add_locale_headers(headers: MutableHeaders, locale: str) -> None:
    """State the locale of a response: ``Content-Language``, and ``Accept-Language`` appended to ``Vary``."""
    headers["Content-Language"] = locale
    headers.append("Vary", "Accept-Language")


class LocaleNegotiation:
    """ASGI middleware that negotiates the locale once per request and states it on every response.

    It runs outside the request checks, so a request they reject, an unrouted path and a preflight answer carry the
    headers too. The chosen tag is stored in the request's state for the handlers that serve engine text.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Keep the application the middleware wraps."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Negotiate the locale of an HTTP request and add its headers to the response start."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        header = ", ".join(Headers(scope=scope).getlist("accept-language")) or None
        locale = negotiate_locale(header)
        scope.setdefault("state", {})[LOCALE_STATE_KEY] = locale

        async def stating(message: Message) -> None:
            if message["type"] == "http.response.start":
                add_locale_headers(MutableHeaders(scope=message), locale)
            await send(message)

        await self._app(scope, receive, stating)


__all__ = ["LOCALE_STATE_KEY", "LocaleNegotiation", "add_locale_headers", "locale_of", "negotiate_locale"]
