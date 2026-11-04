"""The ``watchlist list --json`` document: a bare array, written with the shared timestamp spelling."""

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.workspace.runs import WatchlistSummary
from investment_analysis_engine.workspace_documents.json_documents import JSON_DOCUMENTS
from investment_analysis_engine.workspace_documents.watchlist import (
    WatchlistListDocument,
    build_watchlist_list_document,
)
from scripts.generate_schemas import expected_schemas

runner = CliRunner()

_CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_the_list_is_a_versioned_object_and_an_empty_list_has_no_items() -> None:
    assert build_watchlist_list_document(()).model_dump(mode="json") == {"schema_version": 1, "items": []}
    summary = WatchlistSummary(
        watchlist_id=UUID(int=1), display_name="Core", entry_count=2, created_at=_CREATED, updated_at=None
    )
    document = build_watchlist_list_document((summary,)).model_dump(mode="json")
    assert list(document) == ["schema_version", "items"]
    assert document["items"] == [
        {
            "watchlist_id": "00000000-0000-0000-0000-000000000001",
            "display_name": "Core",
            "entry_count": 2,
            "created_at": "2026-01-02T03:04:05+00:00",
            "updated_at": None,
        }
    ]


def test_the_document_is_published_for_the_command_as_a_version_one_object() -> None:
    assert JSON_DOCUMENTS["watchlist list"].model is WatchlistListDocument
    schema = json.loads(expected_schemas()["watchlist-list.schema.json"])
    assert "unversioned" not in schema["description"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == 1
    assert set(schema["properties"]) == {"schema_version", "items"}
    assert "has_more" not in schema["properties"]


@pytest.mark.usefixtures("isolated_cli_settings")
def test_the_command_output_validates_as_the_document_and_keeps_the_offset() -> None:
    empty = runner.invoke(app, ["watchlist", "list", "--json"])
    assert (empty.exit_code, empty.stdout.strip()) == (0, '{"schema_version": 1, "items": []}')

    for name in ("Core", "Other"):
        assert runner.invoke(app, ["watchlist", "create", name]).exit_code == 0
    result = runner.invoke(app, ["watchlist", "list", "--json"])

    assert result.exit_code == 0, result.output
    document = WatchlistListDocument.model_validate_json(result.stdout)
    assert {item.display_name for item in document.items} == {"Core", "Other"}
    assert all(item["created_at"].endswith("+00:00") for item in json.loads(result.stdout)["items"])
