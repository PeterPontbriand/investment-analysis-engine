"""The reviewed Graham growth-value Golden-Suite case."""

from typing import Final

from src.evaluation.composition import GRAHAM_FACTS_FIXTURE_ID, KNOWN_ETF_PROFILE_FIXTURE_ID
from src.evaluation.models import (
    Case,
    DomainOutcomeExpectation,
    Expectation,
    GrahamMethod,
    GrahamMethodConstraints,
    NumericalExpectation,
    ToolConstraints,
    ToolName,
)

_GROWTH_TOOL_CONSTRAINTS: Final = ToolConstraints(
    permitted=(ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,),
    required=(ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,),
)
_GROWTH_METHOD_CONSTRAINTS: Final = GrahamMethodConstraints(
    permitted=(GrahamMethod.GRAHAM_GROWTH_VALUE,),
    required=(GrahamMethod.GRAHAM_GROWTH_VALUE,),
)


GRG_01: Final = Case(
    case_id="GRG-01",
    description=(
        "Proves the forecast-dependent growth method, explicit assumptions, yield adjustment, and discrimination "
        "from the Graham Number."
    ),
    task="Analyze SYNTH with Graham growth-value using TTM EPS, expected growth 6.5, and current AAA yield 4.15.",
    fixture_ids=(GRAHAM_FACTS_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GROWTH_TOOL_CONSTRAINTS,
        graham_method_constraints=_GROWTH_METHOD_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(field_path="assembly.eps.value", expected_value=4.80, absolute_tolerance=0.0),
            NumericalExpectation(
                field_path="assembly.expected_growth.value",
                expected_value=6.5,
                absolute_tolerance=0.0,
            ),
            NumericalExpectation(
                field_path="assembly.current_aaa_yield.value",
                expected_value=4.15,
                absolute_tolerance=0.0,
            ),
            NumericalExpectation(field_path="policy.base_pe", expected_value=8.5, absolute_tolerance=0.0),
            NumericalExpectation(field_path="policy.growth_multiplier", expected_value=2.0, absolute_tolerance=0.0),
            NumericalExpectation(
                field_path="policy.baseline_aaa_yield",
                expected_value=4.4,
                absolute_tolerance=0.0,
            ),
            NumericalExpectation(
                field_path="result.growth_value",
                expected_value=109.41686746987952,
                absolute_tolerance=1e-9,
            ),
            NumericalExpectation(
                field_path="margin_of_safety_percent",
                expected_value=52.20115398167724,
                absolute_tolerance=1e-9,
            ),
        ),
    ),
    tags=("graham_growth_value", "method_discrimination", "ttm"),
)


GRG_ETF_01: Final = Case(
    case_id="GRG-ETF-01",
    description=(
        "Completes the provider-confirmed ETF applicability matrix for the company-level Graham growth-value "
        "method without resolving company facts."
    ),
    task="Analyze FLSW with the Graham growth-value method using explicit growth and yield assumptions.",
    fixture_ids=(KNOWN_ETF_PROFILE_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GROWTH_TOOL_CONSTRAINTS,
        graham_method_constraints=_GROWTH_METHOD_CONSTRAINTS,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="assembly.status", expected_value="not_applicable"),
            DomainOutcomeExpectation(field_path="margin_of_safety_percent", expected_value=None),
            DomainOutcomeExpectation(field_path="result.growth_value", expected_value=None),
            DomainOutcomeExpectation(
                field_path="result.reason",
                expected_value=(
                    "Graham growth-value method is a company-level valuation method and does not apply directly "
                    "to an ETF. No constituent-level or aggregate ETF valuation was performed."
                ),
            ),
            DomainOutcomeExpectation(field_path="result.status", expected_value="not_applicable"),
        ),
    ),
    tags=("etf", "graham_growth_value", "not_applicable"),
)


GRAHAM_GROWTH_CASES: Final[tuple[Case, ...]] = (GRG_01, GRG_ETF_01)


__all__ = ["GRAHAM_GROWTH_CASES", "GRG_01", "GRG_ETF_01"]
