"""Canonical deterministic Step 2.5 Golden-Suite catalog and request builder."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from src.analysis.fcf_earnings_growth import HistoricalHorizon
from src.core.telemetry import TrajectoryRecorder
from src.evaluation.cases import (
    FCF_01,
    FCF_02,
    FCF_03,
    FCF_ETF_01,
    FPI_01,
    FPI_02,
    FPI_03,
    FPI_04,
    GRA_ETF_01,
    GRG_01,
    GRG_ETF_01,
    GRN_01,
    GRN_02,
    GRN_03,
    GRN_04,
    GRN_05,
    MOMENTUM_BOUNDARY_CASE,
    MOMENTUM_ETF_CASE,
    MOMENTUM_SUCCESS_CASE,
)
from src.evaluation.fixtures.fcf_earnings_growth import FCF_GROWTH_HISTORICAL_AS_OF
from src.evaluation.fixtures.graham import (
    GOLDEN_HISTORICAL_AS_OF,
    GOLDEN_PRECEDENCE_EPS_OVERRIDE,
    NOW,
    SECURITY_ID,
)
from src.evaluation.fixtures.market_data import MOMENTUM_LONG_WINDOW, MOMENTUM_RSI_PERIOD, MOMENTUM_SHORT_WINDOW
from src.evaluation.models import Case
from src.evaluation.reporting import EvaluationReport
from src.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from src.orchestrator.analysis_tools import (
    FCFEarningsGrowthToolArguments,
    GrahamGrowthValueToolArguments,
    GrahamNumberToolArguments,
    MomentumToolArguments,
)

DETERMINISTIC_SUITE_ID: Final = "step-2.5-golden-minimum"
DETERMINISTIC_SUITE_VERSION: Final = "h1-v3"
DETERMINISTIC_FIXTURE_SET_VERSION: Final = "step-2.5-h1-v3"

DETERMINISTIC_CASES: Final[tuple[Case, ...]] = (
    MOMENTUM_SUCCESS_CASE,
    MOMENTUM_BOUNDARY_CASE,
    MOMENTUM_ETF_CASE,
    GRN_01,
    GRN_02,
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


def build_deterministic_requests() -> tuple[DeterministicCaseRequest, ...]:
    """Build the exact production arguments for all nineteen reviewed cases."""
    return tuple(DeterministicCaseRequest(case=case, arguments=_arguments(case)) for case in DETERMINISTIC_CASES)


async def run_minimum_deterministic_suite(
    *,
    executed_at: datetime,
    recorder: TrajectoryRecorder,
) -> EvaluationReport:
    """Execute the canonical nineteen-case deterministic suite and return one report."""
    return await run_deterministic_suite(
        build_deterministic_requests(),
        suite_id=DETERMINISTIC_SUITE_ID,
        suite_version=DETERMINISTIC_SUITE_VERSION,
        fixture_set_version=DETERMINISTIC_FIXTURE_SET_VERSION,
        executed_at=executed_at,
        recorder=recorder,
    )


def _arguments(  # noqa: PLR0911
    case: Case,
) -> (
    MomentumToolArguments | GrahamNumberToolArguments | GrahamGrowthValueToolArguments | FCFEarningsGrowthToolArguments
):
    """Return the reviewed strict production arguments for one canonical case."""
    if case.case_id in {"MOM-01", "MOM-02", "MOM-ETF-01"}:
        return MomentumToolArguments(
            ticker="FLSW" if case.case_id == "MOM-ETF-01" else "MOM",
            short_window=MOMENTUM_SHORT_WINDOW,
            long_window=MOMENTUM_LONG_WINDOW,
            rsi_period=MOMENTUM_RSI_PERIOD,
        )
    if case.case_id in {"GRN-01", "GRN-02", "GRA-ETF-01", "GRN-03"}:
        return GrahamNumberToolArguments(
            ticker=(
                "FLSW" if case.case_id == "GRA-ETF-01" else "MISSING_QUOTE" if case.case_id == "GRN-03" else SECURITY_ID
            ),
            eps_basis="ttm" if case.case_id == "GRN-02" else "three_year_average",
        )
    if case.case_id in {"GRG-01", "GRG-ETF-01"}:
        return GrahamGrowthValueToolArguments(
            ticker="FLSW" if case.case_id == "GRG-ETF-01" else SECURITY_ID,
            eps_basis="ttm",
            expected_growth=6.5,
            current_aaa_yield=4.15,
        )
    if case.case_id == "GRN-04":
        return GrahamNumberToolArguments(
            ticker=SECURITY_ID,
            as_of=NOW,
            eps_override=GOLDEN_PRECEDENCE_EPS_OVERRIDE,
        )
    if case.case_id == "GRN-05":
        return GrahamNumberToolArguments(ticker=SECURITY_ID, as_of=GOLDEN_HISTORICAL_AS_OF)
    if case.case_id in {"FCF-01", "FCF-02", "FCF-03", "FCF-ETF-01"}:
        return FCFEarningsGrowthToolArguments(
            ticker="FLSW" if case.case_id == "FCF-ETF-01" else "ACME",
            historical_horizon=(
                HistoricalHorizon.FOUR_YEARS if case.case_id == "FCF-03" else HistoricalHorizon.LONGEST_AVAILABLE
            ),
            as_of=FCF_GROWTH_HISTORICAL_AS_OF if case.case_id == "FCF-03" else None,
        )
    if case.case_id in {"FPI-01", "FPI-02", "FPI-04"}:
        return GrahamGrowthValueToolArguments(
            ticker={"FPI-01": "ASML", "FPI-02": "NTR", "FPI-04": "NVO"}[case.case_id],
            eps_basis="fiscal_year",
            expected_growth=6.5,
            current_aaa_yield=4.15,
            current_price_override=100.0 if case.case_id == "FPI-04" else None,
        )
    if case.case_id == "FPI-03":
        return FCFEarningsGrowthToolArguments(ticker="SAP", currency="EUR")
    raise ValueError(f"Case {case.case_id!r} is not part of the canonical deterministic catalog.")


__all__ = [
    "DETERMINISTIC_CASES",
    "DETERMINISTIC_FIXTURE_SET_VERSION",
    "DETERMINISTIC_SUITE_ID",
    "DETERMINISTIC_SUITE_VERSION",
    "build_deterministic_requests",
    "run_minimum_deterministic_suite",
]
