"""Generate the checked-in JSON schemas of the command line's ``--json`` documents, or check them for drift.

Each document has one file under ``schemas/``, named for the document and produced from its typed model
with ``model_json_schema(mode="serialization")``, serialized with sorted keys, two-space indent and a
trailing line feed. The drift test compares these exact bytes with the files, so a model change that is
not followed by a regeneration fails the standard test run.

Usage, as a module from the repository root::

    uv run python -m scripts.generate_schemas          # write every schema
    uv run python -m scripts.generate_schemas --check  # report schemas that are missing or out of date

This is a developer script, not an ``ian`` command.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from investment_analysis_engine.workspace_documents.json_documents import DOCUMENTS as GENERIC_DOCUMENTS
from scripts.repository_root import REPOSITORY_ROOT

SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas"


def strategy_schema_file(descriptor: StrategyDescriptor) -> str:
    """Return the schema file of a strategy's document, named for the strategy's command alias."""
    return f"{descriptor.alias}.schema.json"


SELECTION_SCHEMA_DIRECTORY_NAME = "selections"
"""The folder of ``schemas/`` that holds one selection schema per strategy."""

FIXED_SELECTION_FIELDS = ("analysis_id", "method_id", "config_schema_version")
"""The fields a selection's class fixes; a client does not supply them and the schemas leave them out."""


def selection_schema_file(descriptor: StrategyDescriptor) -> str:
    """Return the schema file of a strategy's selection, under ``selections/`` and named for its command alias."""
    return f"{SELECTION_SCHEMA_DIRECTORY_NAME}/{descriptor.alias}.schema.json"


def selection_schema(descriptor: StrategyDescriptor) -> dict[str, Any]:
    """Return the schema of the fields ``build_selection`` accepts for a strategy.

    It is the selection model's own schema with the fixed fields removed, ``as_of`` described as a date or a
    date-time with a timezone offset, and the fields the settings fill carrying neither a ``default`` nor a place in
    ``required``: the configured value is the caller's to ask for, not the schema's to state.
    """
    schema: dict[str, Any] = descriptor.behavior.selection_type.model_json_schema(mode="validation")
    properties: dict[str, Any] = schema["properties"]
    for name in FIXED_SELECTION_FIELDS:
        properties.pop(name, None)
    as_of = properties["as_of"]
    properties["as_of"] = {
        key: value
        for key, value in {
            "anyOf": [
                {"type": "string", "format": "date"},
                {"type": "string", "format": "date-time"},
                {"type": "null"},
            ],
            "default": as_of.get("default"),
            "description": as_of.get("description"),
            "title": as_of.get("title"),
        }.items()
        if value is not None or key == "default"
    }
    for name in descriptor.selection_settings_fields:
        properties[name].pop("default", None)
    required = [
        name
        for name in schema.get("required", [])
        if name not in FIXED_SELECTION_FIELDS and name not in descriptor.selection_settings_fields
    ]
    if required:
        schema["required"] = required
    else:
        schema.pop("required", None)
    return schema


def selection_schema_text(descriptor: StrategyDescriptor) -> str:
    """Return the canonical text of a strategy's selection schema."""
    return (
        json.dumps(selection_schema(descriptor), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    )


# One entry per document: the file name and the typed model it describes. The failure, workspace and database documents
# come from the table in ``investment_analysis_engine/workspace_documents/json_documents.py``; each strategy's model is
# its descriptor's ``json_envelope``, added here because only the composition root may read the descriptors.
DOCUMENTS: tuple[tuple[str, type[BaseModel]], ...] = (
    *((document.schema_file, document.model) for document in GENERIC_DOCUMENTS),
    *((strategy_schema_file(item), item.json_envelope) for item in STRATEGIES),
)


def schema_text(model: type[BaseModel]) -> str:
    """Return the canonical schema text of ``model``: sorted keys, two-space indent, trailing line feed."""
    schema = model.model_json_schema(mode="serialization")
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def expected_schemas() -> dict[str, str]:
    """Return the schema text of every document, keyed by file name."""
    texts = {name: schema_text(model) for name, model in DOCUMENTS}
    texts.update({selection_schema_file(item): selection_schema_text(item) for item in STRATEGIES})
    return texts


def schema_gaps(directory: Path = SCHEMA_DIRECTORY) -> list[str]:
    """Return one message per schema file that is missing or differs from the regenerated text.

    Line endings are compared as written: the repository stores these files with line feeds.
    """
    gaps: list[str] = []
    for name, text in expected_schemas().items():
        path = directory / name
        if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
            gaps.append(
                f"schema schemas/{name} is missing or out of date; run uv run python -m scripts.generate_schemas"
            )
    return gaps


def write_schemas(directory: Path = SCHEMA_DIRECTORY) -> list[Path]:
    """Write every schema file, returning the paths whose content changed."""
    directory.mkdir(exist_ok=True)
    changed: list[Path] = []
    for name, text in expected_schemas().items():
        path = directory / name
        path.parent.mkdir(exist_ok=True)
        data = text.encode("utf-8")
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
            changed.append(path)
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    """Write the schemas, or with ``--check`` report drift and return 1 when there is any."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="Report missing or out-of-date schemas; write nothing.")
    arguments = parser.parse_args(argv)
    if arguments.check:
        gaps = schema_gaps(SCHEMA_DIRECTORY)
        sys.stderr.write("".join(f"{gap}\n" for gap in gaps))
        return 1 if gaps else 0
    changed = write_schemas(SCHEMA_DIRECTORY)
    sys.stdout.write("".join(f"wrote {path.name}\n" for path in changed) or "schemas are current\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
