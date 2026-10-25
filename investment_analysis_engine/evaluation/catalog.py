"""Canonical deterministic Step 2.5 Golden-Suite catalog and request builder."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Final

from investment_analysis_engine.evaluation.cases.fcf_growth import (
    FCF_01,
    FCF_02,
    FCF_03,
    FCF_ETF_01,
    FCF_GROWTH_ARGUMENTS,
    FPI_03,
)
from investment_analysis_engine.evaluation.cases.graham_growth import (
    FPI_01,
    FPI_02,
    FPI_04,
    GRAHAM_GROWTH_ARGUMENTS,
    GRG_01,
    GRG_ETF_01,
)
from investment_analysis_engine.evaluation.cases.graham_number import (
    GRA_ETF_01,
    GRAHAM_NUMBER_ARGUMENTS,
    GRN_01,
    GRN_03,
    GRN_04,
    GRN_05,
)
from investment_analysis_engine.evaluation.cases.momentum import (
    MOMENTUM_ARGUMENTS,
    MOMENTUM_BOUNDARY_CASE,
    MOMENTUM_ETF_CASE,
    MOMENTUM_SUCCESS_CASE,
)
from investment_analysis_engine.evaluation.models import Case
from investment_analysis_engine.evaluation.reporting import EvaluationReport
from investment_analysis_engine.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from investment_analysis_engine.orchestrator.analysis_tool_arguments import AnalysisToolArguments
from investment_analysis_engine.telemetry.recorder import TrajectoryRecorder

DETERMINISTIC_SUITE_ID: Final = "step-2.5-golden-minimum"
DETERMINISTIC_SUITE_VERSION: Final = "h1-v6"
DETERMINISTIC_FIXTURE_SET_VERSION: Final = "step-2.5-h1-v4"

DETERMINISTIC_CASES: Final[tuple[Case, ...]] = (
    MOMENTUM_SUCCESS_CASE,
    MOMENTUM_BOUNDARY_CASE,
    MOMENTUM_ETF_CASE,
    GRN_01,
    GRA_ETF_01,
    GRN_03,
    GRG_01,
    GRG_ETF_01,
    GRN_04,
    GRN_05,
    FCF_01,
    FCF_02,
    FCF_03,
    FCF_ETF_01,
    FPI_01,
    FPI_02,
    FPI_03,
    FPI_04,
)


def _merge_arguments(*tables: Mapping[str, AnalysisToolArguments]) -> Mapping[str, AnalysisToolArguments]:
    """Combine the case modules' reviewed arguments, rejecting a case id that two modules both claim."""
    merged: dict[str, AnalysisToolArguments] = {}
    for table in tables:
        for case_id, arguments in table.items():
            if case_id in merged:
                raise ValueError(f"Case {case_id!r} has reviewed arguments in more than one case module.")
            merged[case_id] = arguments
    return MappingProxyType(merged)


_REVIEWED_ARGUMENTS: Final = _merge_arguments(
    MOMENTUM_ARGUMENTS,
    GRAHAM_NUMBER_ARGUMENTS,
    GRAHAM_GROWTH_ARGUMENTS,
    FCF_GROWTH_ARGUMENTS,
)


def _reviewed_arguments(case: Case) -> AnalysisToolArguments:
    """Return the reviewed production arguments one case module declares for ``case``."""
    try:
        return _REVIEWED_ARGUMENTS[case.case_id]
    except KeyError:
        raise ValueError(f"Case {case.case_id!r} is not part of the canonical deterministic catalog.") from None


def build_deterministic_requests() -> tuple[DeterministicCaseRequest, ...]:
    """Build the exact production arguments for all eighteen reviewed cases."""
    return tuple(
        DeterministicCaseRequest(case=case, arguments=_reviewed_arguments(case)) for case in DETERMINISTIC_CASES
    )


async def run_minimum_deterministic_suite(
    *,
    executed_at: datetime,
    recorder: TrajectoryRecorder,
) -> EvaluationReport:
    """Execute the canonical eighteen-case deterministic suite and return one report."""
    return await run_deterministic_suite(
        build_deterministic_requests(),
        suite_id=DETERMINISTIC_SUITE_ID,
        suite_version=DETERMINISTIC_SUITE_VERSION,
        fixture_set_version=DETERMINISTIC_FIXTURE_SET_VERSION,
        executed_at=executed_at,
        recorder=recorder,
    )


__all__ = [
    "DETERMINISTIC_CASES",
    "DETERMINISTIC_FIXTURE_SET_VERSION",
    "DETERMINISTIC_SUITE_ID",
    "DETERMINISTIC_SUITE_VERSION",
    "build_deterministic_requests",
    "run_minimum_deterministic_suite",
]
