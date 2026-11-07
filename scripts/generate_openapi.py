"""Generate the checked-in OpenAPI description of the local API, or check it for drift.

The description is OpenAPI 3.1, built from the API's route table with every response declared for each status code,
and written to ``schemas/openapi.json`` with sorted keys, two-space indent and a trailing line feed. The API does not
serve it. The drift test and the managed quality gate compare these exact bytes with the file.

Usage, as a module from the repository root::

    uv run python -m scripts.generate_openapi          # write the description
    uv run python -m scripts.generate_openapi --check  # report a description that is missing or out of date

This is a developer script, not an ``ian`` command.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from investment_analysis_engine.api.documents import API_VERSIONS, AnalysisDocument, installed_engine_version
from investment_analysis_engine.api.routes import ROUTES, RouteSpec
from investment_analysis_engine.api.selection_forms import SelectionFormDocument
from investment_analysis_engine.application.selections import selection_schema
from investment_analysis_engine.strategy_wiring import STRATEGIES
from scripts.repository_root import REPOSITORY_ROOT

OPENAPI_FILE = REPOSITORY_ROOT / "schemas" / "openapi.json"

STATUS_DESCRIPTIONS = {
    200: "The document.",
    201: "The document of what was created.",
    202: "The refresh job was accepted; its document says where it is and the Location header names its URL.",
    400: "A rejected parameter, or a Host or Origin the server does not allow.",
    401: "No valid bearer token.",
    404: "No such resource.",
    409: (
        "The stored data refuses the change: a name already in use, an entry this version cannot read, an empty "
        "watchlist to refresh, or a refresh job already running."
    ),
    405: "The endpoint does not accept this method.",
    500: "An unexpected failure.",
    503: "The database is busy.",
}
"""What each status means, in the words of the description."""


def _reference(key_map: dict[Any, Any], models: tuple[type[BaseModel], ...]) -> dict[str, Any]:
    """Return the schema of a response: a reference, or any one of several references."""
    references = [key_map[(model, "serialization")] for model in models]
    return references[0] if len(references) == 1 else {"anyOf": references}


def _rewrite_references(node: Any, prefix: str) -> Any:
    """Return ``node`` with every ``#/$defs/X`` reference pointing at the component ``<prefix>.X`` instead."""
    if isinstance(node, dict):
        return {
            key: (
                f"#/components/schemas/{prefix}.{value.removeprefix('#/$defs/')}"
                if key == "$ref" and isinstance(value, str) and value.startswith("#/$defs/")
                else _rewrite_references(value, prefix)
            )
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_rewrite_references(item, prefix) for item in node]
    return node


def _refine(schemas: dict[str, Any], key_map: dict[Any, Any]) -> None:
    """Name, in the documents that hold a strategy's own document or selection, the schemas they may hold.

    The analysis document's ``document`` is any strategy's document, and the selection form's ``schema`` is any
    strategy's selection schema; each is declared as a free object in the model, so the description lists the
    alternatives. A selection schema is a component of its own, with its definitions beside it.
    """
    analysis = schemas[key_map[(AnalysisDocument, "serialization")]["$ref"].rsplit("/", 1)[1]]
    analysis["properties"]["document"] = {
        "anyOf": [key_map[(item.json_envelope, "serialization")] for item in STRATEGIES],
        "description": analysis["properties"]["document"]["description"],
    }
    alternatives: list[dict[str, str]] = []
    for item in STRATEGIES:
        schema = selection_schema(item)
        name = str(schema["title"])
        for definition, body in schema.pop("$defs", {}).items():
            schemas[f"{name}.{definition}"] = _rewrite_references(body, name)
        schemas[name] = _rewrite_references(schema, name)
        alternatives.append({"$ref": f"#/components/schemas/{name}"})
    form = schemas[key_map[(SelectionFormDocument, "serialization")]["$ref"].rsplit("/", 1)[1]]
    form["properties"]["schema"] = {"anyOf": alternatives, "description": form["properties"]["schema"]["description"]}


def _operation(route: RouteSpec, key_map: dict[Any, Any]) -> dict[str, Any]:
    """Return the OpenAPI operation of one route."""
    responses: dict[str, Any] = {}
    for status, models in route.responses:
        response: dict[str, Any] = {
            "description": STATUS_DESCRIPTIONS[status],
            "content": {"application/json": {"schema": _reference(key_map, models)}},
        }
        if status == 401:
            response["headers"] = {
                "WWW-Authenticate": {"description": "The challenge: Bearer.", "schema": {"type": "string"}}
            }
        if status == route.success_status and route.location is not None:
            response["headers"] = {"Location": {"description": "The job's URL.", "schema": {"type": "string"}}}
        responses[str(status)] = response
    operation: dict[str, Any] = {
        "operationId": route.operation_id,
        "summary": route.summary,
        "parameters": [
            {
                "name": item.name,
                "in": item.location,
                "required": item.required,
                "description": item.description,
                "schema": item.schema_dict(),
            }
            for item in route.parameters
        ],
        "responses": responses,
    }
    if route.request is not None:
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": key_map[(route.request, "validation")]}},
        }
    return operation


def openapi_description() -> dict[str, Any]:
    """Return the OpenAPI 3.1 description of every route in the table."""
    models = list(dict.fromkeys(model for route in ROUTES for _status, group in route.responses for model in group))
    requests = list(dict.fromkeys(route.request for route in ROUTES if route.request is not None))
    key_map, definitions = models_json_schema(
        [*((model, "serialization") for model in models), *((model, "validation") for model in requests)],
        ref_template="#/components/schemas/{model}",
    )
    schemas: dict[str, Any] = dict(definitions.get("$defs", {}))
    _refine(schemas, key_map)
    paths: dict[str, Any] = {}
    for route in ROUTES:
        paths.setdefault(route.path, {})[route.method.lower()] = _operation(route, key_map)
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Investment Analysis Engine local API",
            "version": f"{installed_engine_version()} ({', '.join(API_VERSIONS)})",
            "description": (
                "The endpoints of `ian serve`. Every request carries the per-launch bearer token. A client "
                "must tolerate unknown fields, unknown values and a higher schema_version."
            ),
        },
        "servers": [{"url": "http://127.0.0.1:{port}", "variables": {"port": {"default": "0"}}}],
        "security": [{"bearerAuth": []}],
        "paths": paths,
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
            "schemas": schemas,
        },
    }


def openapi_text() -> str:
    """Return the canonical text of the description: sorted keys, two-space indent, trailing line feed."""
    return json.dumps(openapi_description(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def openapi_gaps(path: Path = OPENAPI_FILE) -> list[str]:
    """Return a message when the description file is missing or differs from the regenerated text."""
    if path.is_file() and path.read_bytes() == openapi_text().encode("utf-8"):
        return []
    return ["schemas/openapi.json is missing or out of date; run uv run python -m scripts.generate_openapi"]


def write_openapi(path: Path = OPENAPI_FILE) -> bool:
    """Write the description, returning whether the file changed."""
    data = openapi_text().encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(data)
    return True


def main(argv: Sequence[str] | None = None, *, path: Path = OPENAPI_FILE) -> int:
    """Write the description to ``path``, or with ``--check`` report drift and return 1 when there is any."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0] if __doc__ else None)
    parser.add_argument(
        "--check", action="store_true", help="Report a missing or out-of-date description; write nothing."
    )
    arguments = parser.parse_args(argv)
    if arguments.check:
        gaps = openapi_gaps(path)
        sys.stderr.write("".join(f"{gap}\n" for gap in gaps))
        return 1 if gaps else 0
    sys.stdout.write("wrote openapi.json\n" if write_openapi(path) else "openapi.json is current\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
