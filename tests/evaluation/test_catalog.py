"""Canonical minimum-suite and Gate M mutation regressions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.core.telemetry import RunContext, TrajectoryRecorder
from src.core.telemetry.models import TrajectoryEvent
from src.evaluation.catalog import (
    DETERMINISTIC_CASES,
    DETERMINISTIC_FIXTURE_SET_VERSION,
    DETERMINISTIC_SUITE_ID,
    DETERMINISTIC_SUITE_VERSION,
    build_deterministic_requests,
    run_minimum_deterministic_suite,
)
from src.evaluation.models import ComponentKind, ComponentOutcome, ComponentResult, DomainOutcomeExpectation
from src.evaluation.reporting import CaseEvaluationResult, CaseOutcome
from src.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite

EXECUTED_AT = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
RUN_ID = UUID("f0000000-0000-0000-0000-00000000000f")
SESSION_ID = UUID("10000000-0000-0000-0000-000000000010")


class RecordingSink:
    """Accept canonical runner telemetry without persistence."""

    def record(self, event: TrajectoryEvent) -> None:
        """Accept one event."""
        del event

    def flush(self) -> None:
        """Accept a flush request."""

    def close(self) -> None:
        """Accept a close request."""


def _recorder() -> TrajectoryRecorder:
    """Build a stable in-memory recorder."""
    return TrajectoryRecorder(RunContext(run_id=RUN_ID, session_id=SESSION_ID), RecordingSink())


def _component(result: CaseEvaluationResult, kind: ComponentKind) -> ComponentResult:
    """Return one component from a case result."""
    return next(component for component in result.components if component.kind is kind)


def test_canonical_catalog_has_exactly_nineteen_unique_reviewed_cases() -> None:
    """The Gate M denominator and request builder are explicit and stable."""
    expected_ids = (
        "MOM-01",
        "MOM-02",
        "MOM-ETF-01",
        "GRN-01",
        "GRN-02",
        "GRA-ETF-01",
        "GRN-03",
        "GRG-01",
        "GRG-ETF-01",
        "GRN-04",
        "GRN-05",
        "FCF-01",
        "FCF-02",
        "FCF-03",
        "FCF-ETF-01",
        "FPI-01",
        "FPI-02",
        "FPI-03",
        "FPI-04",
    )
    assert tuple(case.case_id for case in DETERMINISTIC_CASES) == expected_ids
    requests = build_deterministic_requests()
    assert tuple(request.case.case_id for request in requests) == expected_ids
    assert len({request.case.case_id for request in requests}) == 19


@pytest.mark.asyncio
async def test_canonical_nineteen_case_suite_produces_one_passing_versioned_report() -> None:
    """One operation executes the complete corrected deterministic Gate M denominator."""
    report = await run_minimum_deterministic_suite(executed_at=EXECUTED_AT, recorder=_recorder())

    assert report.suite_id == DETERMINISTIC_SUITE_ID
    assert report.suite_version == DETERMINISTIC_SUITE_VERSION
    assert report.fixture_set_version == DETERMINISTIC_FIXTURE_SET_VERSION
    assert report.total_cases == 19
    assert report.executed_cases == 19
    assert report.passed_cases == 19
    assert report.failed_cases == 0
    assert report.overall_pass_rate == 1.0
    assert all(result.outcome is CaseOutcome.PASS for result in report.case_results)
    assert all(
        _component(result, ComponentKind.STRATEGY_SELECTION).outcome is ComponentOutcome.NOT_MEASURED
        for result in report.case_results
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "field_path", "wrong_value"),
    [
        ("FCF-03", "execution_status", "ok"),
        ("GRA-ETF-01", "result.reason", "wrong applicability reason"),
        ("FCF-02", "classification", "pass"),
        ("FCF-ETF-01", "execution_status", "ok"),
    ],
)
async def test_canonical_runner_detects_mutated_domain_outcomes(
    case_id: str,
    field_path: str,
    wrong_value: str,
) -> None:
    """Wrong statuses, reasons, classifications, and ETF outcomes fail the report."""
    original_request = next(request for request in build_deterministic_requests() if request.case.case_id == case_id)
    mutated_outcomes = tuple(
        DomainOutcomeExpectation(field_path=item.field_path, expected_value=wrong_value)
        if item.field_path == field_path
        else item
        for item in original_request.case.expectation.domain_outcome_expectations
    )
    assert mutated_outcomes != original_request.case.expectation.domain_outcome_expectations
    mutated_expectation = original_request.case.expectation.model_copy(
        update={"domain_outcome_expectations": mutated_outcomes}
    )
    mutated_case = original_request.case.model_copy(update={"expectation": mutated_expectation})
    report = await run_deterministic_suite(
        (DeterministicCaseRequest(case=mutated_case, arguments=original_request.arguments),),
        suite_id="step-2.5-domain-mutation",
        suite_version=DETERMINISTIC_SUITE_VERSION,
        fixture_set_version=DETERMINISTIC_FIXTURE_SET_VERSION,
        executed_at=EXECUTED_AT,
        recorder=_recorder(),
    )

    result = report.case_results[0]
    assert result.outcome is CaseOutcome.FAIL
    execution = _component(result, ComponentKind.EXECUTION_STATUS)
    assert execution.outcome is ComponentOutcome.FAIL
    assert execution.failure_reason is not None
    assert field_path in execution.failure_reason
