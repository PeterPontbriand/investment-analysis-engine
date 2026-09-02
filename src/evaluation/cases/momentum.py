"""The reviewed minimum Momentum Golden-Suite cases."""

from typing import Final

from src.evaluation.composition import (
    KNOWN_ETF_PROFILE_FIXTURE_ID,
    MOMENTUM_BOUNDARY_FIXTURE_ID,
    MOMENTUM_SUCCESS_FIXTURE_ID,
)
from src.evaluation.models import (
    Case,
    DomainOutcomeExpectation,
    Expectation,
    NumericalExpectation,
    ToolConstraints,
    ToolName,
)

_MOMENTUM_TOOL_CONSTRAINTS: Final = ToolConstraints(
    permitted=(ToolName.ANALYZE_MOMENTUM,),
    required=(ToolName.ANALYZE_MOMENTUM,),
)


MOMENTUM_SUCCESS_CASE: Final = Case(
    case_id="MOM-01",
    description=(
        "Proves successful deterministic Momentum arithmetic and distinguishes a valid rising-price analysis "
        "from unavailable history."
    ),
    task="Analyze the supplied rising price history with Momentum and report its structured metrics.",
    fixture_ids=(MOMENTUM_SUCCESS_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_MOMENTUM_TOOL_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(
                field_path="metrics.current_price",
                expected_value=104.0,
                absolute_tolerance=1e-12,
            ),
            NumericalExpectation(
                field_path="metrics.short_sma_val",
                expected_value=103.5,
                absolute_tolerance=1e-12,
            ),
            NumericalExpectation(
                field_path="metrics.long_sma_val",
                expected_value=103.0,
                absolute_tolerance=1e-12,
            ),
            NumericalExpectation(
                field_path="metrics.crossover_signal",
                expected_value=0.0,
                absolute_tolerance=1e-12,
            ),
            NumericalExpectation(
                field_path="metrics.rsi_result.value",
                expected_value=100.0,
                absolute_tolerance=1e-12,
            ),
        ),
    ),
    tags=("momentum", "rising_trend", "success"),
)


MOMENTUM_BOUNDARY_CASE: Final = Case(
    case_id="MOM-02",
    description=(
        "Proves boundary behavior: an available short SMA does not justify a trend or crossover when the long "
        "window is unavailable."
    ),
    task="Analyze the supplied boundary price history with Momentum and report structured availability statuses.",
    fixture_ids=(MOMENTUM_BOUNDARY_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_MOMENTUM_TOOL_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(
                field_path="metrics.current_price",
                expected_value=101.0,
                absolute_tolerance=1e-12,
            ),
            NumericalExpectation(
                field_path="metrics.short_sma_val",
                expected_value=100.5,
                absolute_tolerance=1e-12,
            ),
        ),
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="metrics.crossover_signal", expected_value=None),
            DomainOutcomeExpectation(field_path="metrics.long_sma_val", expected_value=None),
            DomainOutcomeExpectation(
                field_path="metrics.rsi_result.reason_code",
                expected_value="insufficient_history",
            ),
            DomainOutcomeExpectation(field_path="metrics.rsi_result.status", expected_value="unavailable"),
            DomainOutcomeExpectation(field_path="metrics.status", expected_value="UNKNOWN"),
        ),
    ),
    tags=("boundary", "insufficient_history", "momentum"),
)


MOMENTUM_ETF_CASE: Final = Case(
    case_id="MOM-ETF-01",
    description=(
        "Completes the provider-confirmed ETF applicability matrix by proving that Momentum remains applicable "
        "and executes against deterministic price evidence."
    ),
    task="Analyze FLSW with Momentum using the supplied deterministic price history.",
    fixture_ids=(KNOWN_ETF_PROFILE_FIXTURE_ID, MOMENTUM_SUCCESS_FIXTURE_ID),
    expectation=Expectation(
        tool_constraints=_MOMENTUM_TOOL_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(field_path="metrics.current_price", expected_value=104.0, absolute_tolerance=1e-12),
            NumericalExpectation(field_path="metrics.short_sma_val", expected_value=103.5, absolute_tolerance=1e-12),
            NumericalExpectation(field_path="metrics.long_sma_val", expected_value=103.0, absolute_tolerance=1e-12),
        ),
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="instrument_profile.kind_evidence.kind", expected_value="etf"),
            DomainOutcomeExpectation(field_path="metrics.status", expected_value="BULLISH"),
        ),
    ),
    tags=("applicable", "etf", "momentum"),
)


MOMENTUM_CASES: Final[tuple[Case, ...]] = (
    MOMENTUM_SUCCESS_CASE,
    MOMENTUM_BOUNDARY_CASE,
    MOMENTUM_ETF_CASE,
)

__all__ = [
    "MOMENTUM_BOUNDARY_CASE",
    "MOMENTUM_CASES",
    "MOMENTUM_ETF_CASE",
    "MOMENTUM_SUCCESS_CASE",
]
