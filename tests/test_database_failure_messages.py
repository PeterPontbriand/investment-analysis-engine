"""A database failure states only the database's state; the command line adds the target and the remedy."""

import json
import re
from pathlib import Path

import pytest

from investment_analysis_engine.cli_support import database_message
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError, ReadinessReason
from investment_analysis_engine.reporting.failure_envelope import failure_envelope

_PATH = Path("C:/Users/someone/AppData/Local/ian/ian.sqlite3")
_ENVIRONMENT_VARIABLE = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b")
_FILE_PATH = re.compile(r"[A-Za-z]:[\\/]|(?:^|\s)/[\w.-]+/|\\\\|\.sqlite3?\b")


@pytest.mark.parametrize("reason", list(ReadinessReason))
def test_the_served_reason_names_no_command_option_variable_or_path(reason: ReadinessReason) -> None:
    error = DatabaseReadinessError(reason, _PATH, "0006_example")

    envelope = failure_envelope(error.reason_code, str(error), cause=error)

    assert envelope.reason_code.value == reason.value
    assert envelope.reason == str(error)
    assert "ian " not in envelope.reason
    assert "--" not in envelope.reason
    assert _ENVIRONMENT_VARIABLE.search(envelope.reason) is None
    assert _FILE_PATH.search(envelope.reason) is None
    assert str(_PATH) not in envelope.reason
    assert envelope.database is not None
    assert envelope.database.database_path == str(_PATH)


@pytest.mark.parametrize("reason", list(ReadinessReason))
def test_the_command_line_form_of_the_same_failure_keeps_the_target_and_the_remedy(reason: ReadinessReason) -> None:
    error = DatabaseReadinessError(reason, _PATH, "0006_example")

    text = database_message(error)

    assert text.startswith(f"Database {json.dumps(str(_PATH), ensure_ascii=False)}: ")
    assert ("\n\n    ian db upgrade\n\n" in text) is (reason is ReadinessReason.UPGRADE_REQUIRED)
    assert ("--database-url" in text) is (reason is ReadinessReason.UPGRADE_REQUIRED)
    assert "0006_example" in text or reason is not ReadinessReason.UPGRADE_REQUIRED


def test_the_command_line_names_an_in_memory_database_and_an_unknown_revision() -> None:
    error = DatabaseReadinessError(ReadinessReason.UPGRADE_REQUIRED, None)

    assert database_message(error).startswith("Database in-memory database: schema upgrade required to revision the")
    assert "the required revision" in str(error)
