"""The reviewed Piotroski F-Score Golden-Suite cases and their production arguments.

The expected values were computed independently of the calculation, from the captured Company Facts of each issuer.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Final

from investment_analysis_engine.evaluation.fixtures.sec_edgar_statements import (
    STATEMENTS_APPLE_FIXTURE_ID,
    STATEMENTS_MONSTER_FIXTURE_ID,
)
from investment_analysis_engine.evaluation.models import (
    Case,
    DomainOutcomeExpectation,
    Expectation,
    NumericalExpectation,
    ToolConstraints,
)
from investment_analysis_engine.orchestrator.tool_names import ToolName
from investment_analysis_engine.strategies.piotroski.tool import PiotroskiToolArguments

PIOTROSKI_APPLE_AS_OF: Final = datetime(2025, 1, 15, tzinfo=UTC)
"""A boundary after Apple's fiscal 2024 annual report was filed (2024-11-01)."""

PIOTROSKI_MONSTER_AS_OF: Final = datetime(2026, 3, 31, tzinfo=UTC)
"""A boundary after Monster's fiscal 2025 annual report was filed (2026-02-27)."""

_PIOTROSKI_TOOL_CONSTRAINTS: Final = ToolConstraints(
    permitted=(ToolName.ANALYZE_PIOTROSKI,),
    required=(ToolName.ANALYZE_PIOTROSKI,),
)

PIO_01: Final = Case(
    case_id="PIO-01",
    description=(
        "Proves a complete Piotroski F-Score from three fiscal year-ends of Apple's captured statements: seven of "
        "nine tests pass, with the ROA and current-ratio tests failing."
    ),
    task="Analyze Apple's Piotroski F-Score for fiscal 2024.",
    fixture_ids=(STATEMENTS_APPLE_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_PIOTROSKI_TOOL_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(field_path="f_score.score.value", expected_value=7.0, absolute_tolerance=0.0),
            NumericalExpectation(field_path="f_score.available_count", expected_value=9.0, absolute_tolerance=0.0),
        ),
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="execution_status", expected_value="ok"),
            DomainOutcomeExpectation(field_path="f_score.completeness", expected_value="complete"),
            DomainOutcomeExpectation(field_path="industry_class", expected_value="manufacturer"),
            DomainOutcomeExpectation(field_path="taxonomy", expected_value="us-gaap"),
            DomainOutcomeExpectation(field_path="anchor.accession", expected_value="0000320193-24-000123"),
        ),
    ),
    tags=("piotroski", "complete_score", "sec_edgar"),
)

PIO_02: Final = Case(
    case_id="PIO-02",
    description=(
        "Proves a partial Piotroski F-Score from Monster's captured statements: it tags no net income, so the three "
        "tests that need it are unavailable and the score rests on six tests."
    ),
    task="Analyze Monster's Piotroski F-Score for fiscal 2025.",
    fixture_ids=(STATEMENTS_MONSTER_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_PIOTROSKI_TOOL_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(field_path="f_score.score.value", expected_value=5.0, absolute_tolerance=0.0),
            NumericalExpectation(field_path="f_score.available_count", expected_value=6.0, absolute_tolerance=0.0),
        ),
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="execution_status", expected_value="ok"),
            DomainOutcomeExpectation(field_path="f_score.completeness", expected_value="partial"),
            DomainOutcomeExpectation(field_path="industry_class", expected_value="manufacturer"),
            DomainOutcomeExpectation(field_path="taxonomy", expected_value="us-gaap"),
            DomainOutcomeExpectation(field_path="anchor.accession", expected_value="0001104659-26-020831"),
        ),
    ),
    tags=("piotroski", "partial_score", "sec_edgar"),
)

PIOTROSKI_CASES: Final[tuple[Case, ...]] = (PIO_01, PIO_02)

PIOTROSKI_ARGUMENTS: Final[Mapping[str, PiotroskiToolArguments]] = MappingProxyType(
    {
        "PIO-01": PiotroskiToolArguments(ticker="AAPL", as_of=PIOTROSKI_APPLE_AS_OF),
        "PIO-02": PiotroskiToolArguments(ticker="MNST", as_of=PIOTROSKI_MONSTER_AS_OF),
    }
)
"""The reviewed production arguments of each Piotroski F-Score case, keyed by case id."""

__all__ = ["PIO_01", "PIO_02", "PIOTROSKI_ARGUMENTS", "PIOTROSKI_CASES"]
