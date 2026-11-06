"""The published JSON schemas are generated from the typed models and checked for drift (T20)."""

import json
from pathlib import Path

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.selections import build_selection
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from scripts import generate_schemas
from scripts.generate_schemas import (
    DOCUMENTS,
    FIXED_SELECTION_FIELDS,
    SCHEMA_DIRECTORY,
    expected_schemas,
    schema_gaps,
    selection_schema,
    selection_schema_file,
    write_schemas,
)


def test_published_schemas_are_current() -> None:
    """T20: every checked-in schema is byte-identical to the one regenerated from its model."""
    assert schema_gaps() == []


def test_every_document_has_a_schema_file_and_no_other_file_is_published() -> None:
    names = {name for name, _model in DOCUMENTS}
    # ``openapi.json`` is the API description, generated and checked by scripts/generate_openapi.py.
    assert {path.name for path in SCHEMA_DIRECTORY.glob("*.json")} - {"openapi.json"} == names
    selections = {selection_schema_file(item).split("/")[-1] for item in STRATEGIES}
    assert {path.name for path in (SCHEMA_DIRECTORY / "selections").glob("*.json")} == selections


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
        f"schema schemas/{name} is missing or out of date; run uv run python -m scripts.generate_schemas"
        for name in expected_schemas()
    ]


def test_a_drifted_schema_fails_and_regeneration_repairs_it(tmp_path: Path) -> None:
    write_schemas(tmp_path)
    assert schema_gaps(tmp_path) == []
    drifted = tmp_path / "failure.schema.json"
    drifted.write_bytes(drifted.read_bytes().replace(b"execution_error", b"execution_failure"))
    assert schema_gaps(tmp_path) == [
        "schema schemas/failure.schema.json is missing or out of date; run uv run python -m scripts.generate_schemas"
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


_SAMPLE_VALUES = {
    "expected_growth": 5.0,
    "aaa_yield_override": 4.5,
    "short_window": 5,
    "long_window": 20,
    "rsi_period": 14,
}


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_a_selection_schema_describes_exactly_the_fields_build_selection_accepts(
    descriptor: StrategyDescriptor,
) -> None:
    """Each property is accepted by the builder, and what the schema leaves out is rejected."""
    model = descriptor.behavior.selection_type
    schema = selection_schema(descriptor)
    properties = set(schema["properties"])
    assert properties == set(model.model_fields) - set(FIXED_SELECTION_FIELDS)
    context = ApplicationContext(settings=ProjectSettings())
    required = {
        name: _SAMPLE_VALUES[name] for name in (*schema.get("required", []), *descriptor.selection_settings_fields)
    }
    for name in sorted(properties):
        field = model.model_fields[name]
        value = _SAMPLE_VALUES[name] if field.is_required() else field.get_default(call_default_factory=True)
        if name == "policy":
            value = {}
        build_selection(context, descriptor.method_id, {**required, name: value})
    for name in FIXED_SELECTION_FIELDS:
        with pytest.raises(ValueError, match=name):
            build_selection(context, descriptor.method_id, {**required, name: "x"})


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_a_selection_schema_states_no_default_for_a_field_the_settings_fill(descriptor: StrategyDescriptor) -> None:
    schema = selection_schema(descriptor)
    for name in descriptor.selection_settings_fields:
        assert "default" not in schema["properties"][name]
        assert name not in schema.get("required", [])
    assert set(schema["properties"]["as_of"]["anyOf"][0]) == {"type", "format"}
    assert [part.get("format") for part in schema["properties"]["as_of"]["anyOf"]] == ["date", "date-time", None]
