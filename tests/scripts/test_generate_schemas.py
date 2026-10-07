"""The published JSON schemas are generated from the typed models and checked for drift (T20)."""

import json
from pathlib import Path

import pytest

from scripts import generate_schemas
from scripts.generate_schemas import DOCUMENTS, SCHEMA_DIRECTORY, expected_schemas, schema_gaps, write_schemas
from src.reporting.documents.failure import FailureReasonCode


def test_published_schemas_are_current() -> None:
    """T20: every checked-in schema is byte-identical to the one regenerated from its model."""
    assert schema_gaps() == []


def test_every_document_has_a_schema_file_and_no_other_file_is_published() -> None:
    names = {name for name, _model in DOCUMENTS}
    assert {path.name for path in SCHEMA_DIRECTORY.glob("*.json")} == names


def test_schema_text_uses_sorted_keys_two_space_indent_and_a_trailing_line_feed() -> None:
    for text in expected_schemas().values():
        assert text.endswith("}\n")
        assert not text.endswith("\n\n")
        document = json.loads(text)
        assert text == json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_failure_schema_lists_the_whole_code_enumeration() -> None:
    """A change to a code is visible in the published schema, so the drift check shows it."""
    schema = json.loads(expected_schemas()["failure.schema.json"])
    assert schema["$defs"]["FailureReasonCode"]["enum"] == [item.value for item in FailureReasonCode]
    assert "own lineage" in schema["description"]


def test_a_missing_schema_fails_naming_the_file(tmp_path: Path) -> None:
    gaps = schema_gaps(tmp_path)
    assert gaps == [
        f"schema schemas/{name} is missing or out of date; run scripts/generate_schemas.py"
        for name, _model in DOCUMENTS
    ]


def test_a_drifted_schema_fails_and_regeneration_repairs_it(tmp_path: Path) -> None:
    write_schemas(tmp_path)
    assert schema_gaps(tmp_path) == []
    drifted = tmp_path / "failure.schema.json"
    drifted.write_bytes(drifted.read_bytes().replace(b"execution_error", b"execution_failure"))
    assert schema_gaps(tmp_path) == [
        "schema schemas/failure.schema.json is missing or out of date; run scripts/generate_schemas.py"
    ]
    assert write_schemas(tmp_path) == [drifted]
    assert schema_gaps(tmp_path) == []
    assert write_schemas(tmp_path) == []


def test_a_crlf_copy_is_reported_as_drift(tmp_path: Path) -> None:
    """The comparison is by bytes: the repository stores these files with line feeds."""
    write_schemas(tmp_path)
    copy = tmp_path / "failure.schema.json"
    copy.write_bytes(copy.read_bytes().replace(b"\n", b"\r\n"))
    assert len(schema_gaps(tmp_path)) == 1


def test_check_mode_reports_drift_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(generate_schemas, "SCHEMA_DIRECTORY", tmp_path)
    assert generate_schemas.main(["--check"]) == 1
    assert "failure.schema.json is missing or out of date" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []
    assert generate_schemas.main([]) == 0
    assert "wrote failure.schema.json" in capsys.readouterr().out
    assert generate_schemas.main(["--check"]) == 0
    assert generate_schemas.main([]) == 0
    assert "schemas are current" in capsys.readouterr().out
