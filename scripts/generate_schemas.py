"""Generate the checked-in JSON schemas of the command line's ``--json`` documents, or check them for drift.

Each document has one file under ``schemas/``, named for the document and produced from its typed model
with ``model_json_schema(mode="serialization")``, serialized with sorted keys, two-space indent and a
trailing line feed. The drift test compares these exact bytes with the files, so a model change that is
not followed by a regeneration fails the standard test run.

Usage, from the repository root::

    uv run python scripts/generate_schemas.py          # write every schema
    uv run python scripts/generate_schemas.py --check  # report schemas that are missing or out of date

This is a developer script, not an ``ian`` command.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from src.reporting.json_documents import DOCUMENTS as GENERIC_DOCUMENTS
from src.strategy_wiring import STRATEGIES, StrategyDescriptor

SCHEMA_DIRECTORY = Path(__file__).resolve().parent.parent / "schemas"


def strategy_schema_file(descriptor: StrategyDescriptor) -> str:
    """Return the schema file of a strategy's document, named for the strategy's command alias."""
    return f"{descriptor.alias}.schema.json"


# One entry per document: the file name and the typed model it describes. The failure, workspace and database
# documents come from the table in ``src/reporting/json_documents.py``; each strategy's model is its descriptor's
# ``json_envelope``, added here because only the composition root may read the descriptors.
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
    return {name: schema_text(model) for name, model in DOCUMENTS}


def schema_gaps(directory: Path = SCHEMA_DIRECTORY) -> list[str]:
    """Return one sentence per schema file that is missing or differs from the regenerated text.

    Line endings are compared as written: the repository stores these files with line feeds.
    """
    gaps: list[str] = []
    for name, text in expected_schemas().items():
        path = directory / name
        if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
            gaps.append(f"schema schemas/{name} is missing or out of date; run scripts/generate_schemas.py")
    return gaps


def write_schemas(directory: Path = SCHEMA_DIRECTORY) -> list[Path]:
    """Write every schema file, returning the paths whose content changed."""
    directory.mkdir(exist_ok=True)
    changed: list[Path] = []
    for name, text in expected_schemas().items():
        path = directory / name
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
