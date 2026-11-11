"""The refreshes-list document: its outcome counts follow the run outcomes, and its schema is the checked-in one."""

import json

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.workspace_documents.json_documents import DOCUMENTS
from investment_analysis_engine.workspace_documents.refreshes import RefreshOutcomeCountsDocument
from scripts.repository_root import REPOSITORY_ROOT


def test_there_is_one_count_for_every_run_outcome() -> None:
    assert set(RefreshOutcomeCountsDocument.model_fields) == {outcome.value for outcome in RunOutcome}


def test_the_command_and_its_schema_file_are_listed() -> None:
    listed = {document.schema_file: document.commands for document in DOCUMENTS}

    assert listed["refreshes-list.schema.json"] == ("runs refreshes",)
    schema = json.loads((REPOSITORY_ROOT / "schemas" / "refreshes-list.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == 1
