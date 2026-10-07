"""The failure envelope's code vocabulary (T18) and its closed, report-only shape (T19)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from pydantic import BaseModel, ValidationError

import src.cli  # noqa: F401 - loads every module that defines an exception with a reason_code
from src.data.base_client import DataFetchError
from src.data.market_data import HistoricalMarketData, MarketDataContext, NoEligibleObservationsError
from src.data.quality import (
    DataQualityError,
    HistoricalDataQualityError,
    QualityContext,
    evaluate_historical_quality,
)
from src.data.repositories.readiness import DatabaseReadinessError, ReadinessReason
from src.data.repositories.watchlists import WatchlistConflictError, WatchlistEntryNotFoundError
from src.reporting.analysis_runs import UnsupportedProjectionError
from src.reporting.documents.database import DatabaseMaintenanceReport
from src.reporting.documents.failure import (
    FailureDatabase,
    FailureDiagnostic,
    FailureEnvelope,
    FailureReasonCode,
    status_for,
)
from src.reporting.failure_classification import (
    CLASSIFICATION_RULES,
    AnalysisConfigurationError,
    InvalidParameterError,
    classify_failure,
    failure_envelope,
)
from src.reporting.presentation import failure_document
from src.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError
from src.workspace.refresh import EmptyRefreshTargetError
from src.workspace.watchlists import StoredSelectionError, WatchlistNotFoundError
from tests._cli_helpers import isolated_cli_database, stub_yahoo_identity_metadata  # noqa: F401

# Codes raised by a command with no exception to classify: the run a command looked up does not exist.
_COMMAND_CONTEXT_CODES = {FailureReasonCode.ANALYSIS_RUN_NOT_FOUND}


def _all_exception_types() -> set[type[BaseException]]:
    """Every loaded exception class, found through the subclass tree."""
    found: set[type[BaseException]] = set()
    pending: list[type[BaseException]] = [BaseException]
    while pending:
        for subclass in pending.pop().__subclasses__():
            if subclass not in found:
                found.add(subclass)
                pending.append(subclass)
    return found


def _historical_quality_error() -> HistoricalDataQualityError:
    frame = pd.DataFrame({"Close": [1.0, float("nan")]}, index=pd.date_range("2026-09-09", periods=2))
    decisions = evaluate_historical_quality(
        HistoricalMarketData(frame, MarketDataContext()),
        context=QualityContext("ACME", datetime(2026, 9, 11, tzinfo=UTC)),
    )
    return HistoricalDataQualityError(decisions, frame)


def _sample(exception_type: type[BaseException]) -> BaseException:
    """Return an instance of ``exception_type`` for the classifier."""
    if exception_type is HistoricalDataQualityError:
        return _historical_quality_error()
    return exception_type("sample")


def test_every_readiness_reason_is_a_failure_reason_code() -> None:
    """T18: the database codes of both shapes are one vocabulary."""
    assert {item.value for item in ReadinessReason} <= {item.value for item in FailureReasonCode}
    for reason in ReadinessReason:
        classified = classify_failure(DatabaseReadinessError(reason, Path("x.sqlite3")))
        assert classified.reason_code.value == reason.value
        assert classified.status == "error"


def test_every_exception_reason_code_attribute_is_a_failure_reason_code() -> None:
    """T18: a code an exception carries is classified to itself, so a new one cannot be forgotten."""
    carrying = {
        exception_type
        for exception_type in _all_exception_types()
        if isinstance(exception_type.__dict__.get("reason_code"), str) and exception_type.__module__.startswith("src.")
    }
    assert {InvalidStoredRunError, UnsupportedRunVersionError} <= carrying
    for exception_type in carrying:
        code = FailureReasonCode(exception_type.reason_code)  # type: ignore[attr-defined]
        assert classify_failure(_sample(exception_type)).reason_code is code


def test_every_code_the_classifier_can_return_is_a_member_and_every_member_can_be_returned() -> None:
    """T18: the rules, the readiness codes and the default cover the enumeration, except command-context codes."""
    returned = {code for _type, code in CLASSIFICATION_RULES}
    returned |= {FailureReasonCode(item.value) for item in ReadinessReason}
    returned.add(classify_failure(RuntimeError("unrecognized")).reason_code)
    assert returned | _COMMAND_CONTEXT_CODES == set(FailureReasonCode)
    assert not returned & _COMMAND_CONTEXT_CODES
    assert classify_failure(RuntimeError("unrecognized")).reason_code is FailureReasonCode.EXECUTION_ERROR


@pytest.mark.parametrize(("exception_type", "code"), CLASSIFICATION_RULES)
def test_each_rule_classifies_its_exception_to_its_code(
    exception_type: type[BaseException], code: FailureReasonCode
) -> None:
    classified = classify_failure(_sample(exception_type))
    assert classified.reason_code is code
    assert classified.status == status_for(code)


def test_a_more_specific_exception_is_never_shadowed_by_its_base() -> None:
    """The rules are ordered most specific first: each exception reaches its own rule."""
    for position, (exception_type, code) in enumerate(CLASSIFICATION_RULES):
        for earlier_type, earlier_code in CLASSIFICATION_RULES[:position]:
            assert not issubclass(exception_type, earlier_type) or earlier_code is code, (
                f"{exception_type.__name__} is shadowed by {earlier_type.__name__}"
            )


@pytest.mark.parametrize(
    ("error", "code", "status"),
    [
        (DataFetchError("x"), "provider_error", "input_unavailable"),
        (DataQualityError("x"), "provider_error", "input_unavailable"),
        (NoEligibleObservationsError("x"), "no_eligible_observations", "input_unavailable"),
        (AnalysisConfigurationError("x"), "configuration_error", "error"),
        (InvalidParameterError("x"), "invalid_parameter", "error"),
        (WatchlistNotFoundError("x"), "watchlist_not_found", "error"),
        (WatchlistEntryNotFoundError("x"), "watchlist_entry_not_found", "error"),
        (EmptyRefreshTargetError("x"), "watchlist_empty", "error"),
        (WatchlistConflictError("x"), "watchlist_name_conflict", "error"),
        (StoredSelectionError("x"), "stored_selection_unreadable", "error"),
        (UnsupportedProjectionError("x"), "unsupported_projection", "error"),
        (ValueError("x"), "invalid_input", "error"),
        (RuntimeError("x"), "execution_error", "error"),
    ],
)
def test_classifier_returns_the_documented_code_and_status(error: Exception, code: str, status: str) -> None:
    classified = classify_failure(error)
    assert (classified.reason_code.value, classified.status) == (code, status)


def test_historical_quality_failure_is_input_unavailable_and_keeps_its_rule_diagnostics() -> None:
    error = _historical_quality_error()
    assert classify_failure(error).status == "input_unavailable"
    envelope = failure_envelope(FailureReasonCode.HISTORICAL_QUALITY, str(error), cause=error)
    assert [item.rule for item in envelope.diagnostics] == ["historical.numeric"]
    assert envelope.database is None


def test_database_facts_come_from_the_readiness_error_and_nothing_else() -> None:
    error = DatabaseReadinessError(ReadinessReason.UPGRADE_REQUIRED, Path("data") / "x.sqlite3", "0001_head")
    envelope = failure_envelope(FailureReasonCode.DATABASE_UPGRADE_REQUIRED, str(error), cause=error)
    assert envelope.database == FailureDatabase(
        database_path=str(Path("data") / "x.sqlite3"), expected_revision="0001_head"
    )
    in_memory = failure_envelope(
        FailureReasonCode.DATABASE_BUSY, "busy", cause=DatabaseReadinessError(ReadinessReason.BUSY, None)
    )
    assert in_memory.database == FailureDatabase(database_path=None, expected_revision=None)
    assert failure_envelope(FailureReasonCode.EXECUTION_ERROR, "x", cause=RuntimeError("x")).database is None


def test_the_document_has_the_documented_keys_and_stable_formatting() -> None:
    envelope = failure_envelope(
        FailureReasonCode.PROVIDER_ERROR,
        "No usable history.",
        analysis="momentum",
        method="sma_crossover",
        ticker="ACME",
    )
    text = failure_document(envelope)
    assert json.loads(text) == {
        "schema_version": 6,
        "status": "input_unavailable",
        "reason_code": "provider_error",
        "reason": "No usable history.",
        "analysis": "momentum",
        "method": "sma_crossover",
        "ticker": "ACME",
        "result": None,
        "diagnostics": [],
        "database": None,
    }
    assert text.startswith('{\n  "analysis": "momentum",\n')


def _model_field_names(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields)


def test_envelope_fields_are_exactly_the_documented_set() -> None:
    """T19: a field is added only by changing this reviewed set."""
    assert _model_field_names(FailureEnvelope) == {
        "schema_version",
        "status",
        "reason_code",
        "reason",
        "analysis",
        "method",
        "ticker",
        "result",
        "diagnostics",
        "database",
    }
    assert _model_field_names(FailureDatabase) == {"database_path", "expected_revision"}
    assert _model_field_names(FailureDiagnostic) == {"rule", "reason"}


def test_envelope_has_no_remediation_shaped_field() -> None:
    """T19: the envelope reports a condition and never offers an action."""
    remedies = {"remediation", "remedy", "fix", "command", "action", "next_step", "suggestion", "upgrade", "resolution"}
    for model in (FailureEnvelope, FailureDatabase, FailureDiagnostic):
        assert not remedies & _model_field_names(model)
    with pytest.raises(ValidationError):
        FailureEnvelope.model_validate(
            {"status": "error", "reason_code": "execution_error", "reason": "x", "remediation": "run db upgrade"}
        )


def test_envelope_rejects_a_status_that_does_not_follow_from_the_code() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        FailureEnvelope(status="error", reason_code=FailureReasonCode.PROVIDER_ERROR, reason="x")


def test_database_facts_accompany_only_database_codes() -> None:
    facts = FailureDatabase(database_path="x", expected_revision="y")
    with pytest.raises(ValidationError, match="database"):
        FailureEnvelope(status="error", reason_code=FailureReasonCode.EXECUTION_ERROR, reason="x", database=facts)


def test_maintenance_report_shares_the_envelopes_names_and_code_vocabulary() -> None:
    """The report's stable code and sentence are named as the envelope's are."""
    shared = {"reason_code", "reason"}
    assert shared <= _model_field_names(DatabaseMaintenanceReport) & _model_field_names(FailureEnvelope)
    assert _model_field_names(DatabaseMaintenanceReport) == {
        "command",
        "status",
        "database_path",
        "state",
        "current_revision",
        "expected_revision",
        "reason_code",
        "reason",
        "schema_version",
    }
    assert DatabaseMaintenanceReport.model_fields["schema_version"].default == 2


def test_no_command_remediates_for_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """A readiness failure is reported, and no upgrade is attempted on the caller's behalf."""
    from typer.testing import CliRunner  # noqa: PLC0415 - kept beside the one test that drives the application

    def refuse(*_args: object, **_kwargs: object) -> None:
        pytest.fail("db upgrade must never run for a caller")

    monkeypatch.setattr("src.data.repositories.readiness.upgrade_database", refuse)
    monkeypatch.setattr("src.cli_database.upgrade_database", refuse)
    error = DatabaseReadinessError(ReadinessReason.UPGRADE_REQUIRED, Path("x.sqlite3"), "0001_head")
    monkeypatch.setattr("src.cli_support.ensure_database_ready", lambda _database: (_ for _ in ()).throw(error))
    result = CliRunner().invoke(src.cli.app, ["graham-number", "ACME", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["reason_code"] == "database_upgrade_required"


def test_invalid_parameter_and_invalid_input_stay_distinct() -> None:
    """``invalid_parameter`` is an option the command rejected itself; ``invalid_input`` is bad data.

    ``InvalidParameterError`` is a ``ValueError``, so only its place in the ordered rules keeps it from being reported
    as ``invalid_input``. Pinning both directions keeps a caller able to tell a mistake in its own request (fix the
    option) from invalid data (retry later or report it).
    """
    assert issubclass(InvalidParameterError, ValueError)
    assert classify_failure(InvalidParameterError("x")).reason_code is FailureReasonCode.INVALID_PARAMETER
    assert classify_failure(ValueError("x")).reason_code is FailureReasonCode.INVALID_INPUT
    parameter_position = [exception_type for exception_type, _code in CLASSIFICATION_RULES].index(InvalidParameterError)
    value_error_position = [exception_type for exception_type, _code in CLASSIFICATION_RULES].index(ValueError)
    assert parameter_position < value_error_position
