"""The request bodies of the action endpoints, and how a body is read.

A body is one JSON object. Each endpoint declares its fields in a strict model that forbids any other, and a field is
named in a rejection by its path, such as ``tickers``, ``selection.short_window`` or ``tickers[1]``. A rejection here is
a plain ``InvalidParameterError``: it comes from the shape of the request, not from a rule of an application action.
"""

import json
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from investment_analysis_engine.core.operator_errors import InvalidParameterError

BODY_PARAMETER = "body"
"""The parameter a body that is missing, not JSON or not an object is reported under."""

JSON_MEDIA_TYPE = "application/json"
"""The one media type a body may have."""


class RequestBody(BaseModel):
    """A request body: strict, immutable, and no field beyond those declared."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class WatchlistNameRequest(RequestBody):
    """The body that creates a watchlist or renames one."""

    name: str = Field(description="The watchlist's display name.")


class AddEntriesRequest(RequestBody):
    """The body that adds one entry per ticker for one strategy's selection."""

    method_id: str = Field(description="The strategy's method identifier, as GET /v1/strategies lists it.")
    tickers: list[str] = Field(description="The tickers to add the selection for, one entry each.")
    selection: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "The selection's fields, as GET /v1/strategies/{method_id}/selection describes them. A field left out "
            "takes its configured value; as_of is a date or a timestamp with a timezone offset, as text."
        ),
    )


class RemoveTickersRequest(RequestBody):
    """The body that removes every entry for the given tickers."""

    tickers: list[str] = Field(description="The tickers whose entries are removed, across every strategy.")


class RemoveMethodRequest(RequestBody):
    """The body that removes every entry of one strategy."""

    method_id: str = Field(description="The strategy's method identifier, as GET /v1/strategies lists it.")


class AnalysisRequest(RequestBody):
    """The body that analyzes one ticker under one selection."""

    ticker: str = Field(description="The ticker to analyze.")
    method_id: str = Field(description="The strategy's method identifier, as GET /v1/strategies lists it.")
    selection: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "The selection's fields, as GET /v1/strategies/{method_id}/selection describes them. A field left out "
            "takes its configured value; as_of is a date or a timestamp with a timezone offset, as text."
        ),
    )
    save: bool = Field(default=False, description="Whether to keep the result as an Analysis Run.")
    provider_check: bool | None = Field(
        default=None,
        description=(
            "Whether to send one test request to a provider after it fails. When absent or null, the choice made "
            "when the server was launched (IAN_PROVIDER_CHECK) applies, as it does on the command line."
        ),
    )


def _path(location: tuple[int | str, ...]) -> str:
    """Return a pydantic error location as the path a client wrote: ``selection.short_window``, ``tickers[1]``."""
    path = ""
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
    return path


def read_json_object(content_type: str | None, body: bytes) -> Mapping[str, object]:
    """Return the JSON object a request carries.

    Raises:
        InvalidParameterError: If the content type is missing or not ``application/json``, or the body is not one JSON
            object; the parameter is ``body``.
    """
    media_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if media_type != JSON_MEDIA_TYPE:
        raise InvalidParameterError(
            f"The request must have the content type {JSON_MEDIA_TYPE}.", parameters=(BODY_PARAMETER,)
        )
    try:
        document = json.loads(body)
    except ValueError:
        raise InvalidParameterError("The request body must be a JSON object.", parameters=(BODY_PARAMETER,)) from None
    if not isinstance(document, dict):
        raise InvalidParameterError("The request body must be a JSON object.", parameters=(BODY_PARAMETER,))
    return document


def read_request[BodyT: RequestBody](model: type[BodyT], document: Mapping[str, object]) -> BodyT:
    """Return the body ``document`` as ``model``, naming the first rejected field by its path.

    Raises:
        InvalidParameterError: If a field is unknown, missing or of the wrong type.
    """
    try:
        return model.model_validate(document)
    except ValidationError as error:
        first = error.errors(include_input=False, include_url=False)[0]
        field = _path(first["loc"]) or BODY_PARAMETER
        match first["type"]:
            case "extra_forbidden":
                message = f"{field} is not a field of this request."
            case "missing":
                message = f"{field} is required."
            case _:
                message = f"{field} is invalid: {first['msg']}."
        raise InvalidParameterError(message, parameters=(field,)) from None


__all__ = [
    "BODY_PARAMETER",
    "JSON_MEDIA_TYPE",
    "AddEntriesRequest",
    "AnalysisRequest",
    "RemoveMethodRequest",
    "RemoveTickersRequest",
    "RequestBody",
    "WatchlistNameRequest",
    "read_json_object",
    "read_request",
]
