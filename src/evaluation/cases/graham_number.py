"""The reviewed minimum Graham Number Golden-Suite cases."""

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

_GRAHAM_NUMBER_TOOL_CONSTRAINTS: Final = ToolConstraints(
    permitted=(ToolName.ANALYZE_GRAHAM_NUMBER,),
    required=(ToolName.ANALYZE_GRAHAM_NUMBER,),
)
_GRAHAM_NUMBER_METHOD_CONSTRAINTS: Final = GrahamMethodConstraints(
    permitted=(GrahamMethod.GRAHAM_NUMBER,),
    required=(GrahamMethod.GRAHAM_NUMBER,),
)


GRN_01: Final = Case(
    case_id="GRN-01",
    description=(
        "Freezes the standard three-completed-fiscal-year earnings convention and derived EPS lineage for the "
        "Graham Number."
    ),
    task="Analyze SYNTH with Graham Number using the default three-year-average EPS basis.",
    fixture_ids=(GRAHAM_FACTS_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GRAHAM_NUMBER_TOOL_CONSTRAINTS,
        graham_method_constraints=_GRAHAM_NUMBER_METHOD_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(
                field_path="assembly.eps.value",
                expected_value=3.2333333333333333,
                absolute_tolerance=1e-15,
            ),
            NumericalExpectation(
                field_path="result.maximum_indicated_price",
                expected_value=36.68616905592624,
                absolute_tolerance=1e-9,
            ),
            NumericalExpectation(
                field_path="margin_of_safety_percent",
                expected_value=-42.56053806073687,
                absolute_tolerance=1e-9,
            ),
        ),
    ),
    tags=("graham_number", "three_year_average", "success"),
)


GRN_02: Final = Case(
    case_id="GRN-02",
    description=(
        "Proves that the explicit TTM variation uses the retained TTM fact rather than silently averaging fiscal-"
        "year observations."
    ),
    task="Analyze SYNTH with Graham Number using explicitly selected TTM EPS.",
    fixture_ids=(GRAHAM_FACTS_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GRAHAM_NUMBER_TOOL_CONSTRAINTS,
        graham_method_constraints=_GRAHAM_NUMBER_METHOD_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(
                field_path="assembly.eps.value",
                expected_value=4.80,
                absolute_tolerance=0.0,
            ),
            NumericalExpectation(
                field_path="result.maximum_indicated_price",
                expected_value=44.69899327725402,
                absolute_tolerance=1e-9,
            ),
            NumericalExpectation(
                field_path="margin_of_safety_percent",
                expected_value=-17.00487229231157,
                absolute_tolerance=1e-9,
            ),
        ),
    ),
    tags=("graham_number", "success", "ttm"),
)


GRA_ETF_01: Final = Case(
    case_id="GRA-ETF-01",
    description=(
        "Freezes the provider-confirmed ETF applicability boundary: Graham Number is not applicable directly to "
        "an ETF and no company facts are requested."
    ),
    task="Analyze FLSW with Graham Number.",
    fixture_ids=(KNOWN_ETF_PROFILE_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GRAHAM_NUMBER_TOOL_CONSTRAINTS,
        graham_method_constraints=_GRAHAM_NUMBER_METHOD_CONSTRAINTS,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="assembly.status", expected_value="not_applicable"),
            DomainOutcomeExpectation(field_path="margin_of_safety_percent", expected_value=None),
            DomainOutcomeExpectation(field_path="result.maximum_indicated_price", expected_value=None),
            DomainOutcomeExpectation(
                field_path="result.reason",
                expected_value=(
                    "Graham Number is a company-level valuation method and does not apply directly to an ETF. "
                    "No constituent-level or aggregate ETF valuation was performed."
                ),
            ),
            DomainOutcomeExpectation(field_path="result.status", expected_value="not_applicable"),
        ),
    ),
    tags=("graham_number", "not_applicable", "etf"),
)


GRN_03: Final = Case(
    case_id="GRN-03",
    description=(
        "Proves that a missing current quote omits only price comparison; it does not erase a valid Graham Number "
        "or turn an optional input into a required one."
    ),
    task="Analyze MISSING_QUOTE with Graham Number using the default three-year-average EPS basis.",
    fixture_ids=(GRAHAM_FACTS_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GRAHAM_NUMBER_TOOL_CONSTRAINTS,
        graham_method_constraints=_GRAHAM_NUMBER_METHOD_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(
                field_path="result.maximum_indicated_price",
                expected_value=36.68616905592624,
                absolute_tolerance=1e-9,
            ),
        ),
    ),
    tags=("graham_number", "missing_quote", "success"),
)


GRAHAM_NUMBER_CASES: Final[tuple[Case, ...]] = (GRN_01, GRN_02, GRA_ETF_01, GRN_03)

__all__ = ["GRA_ETF_01", "GRAHAM_NUMBER_CASES", "GRN_01", "GRN_02", "GRN_03"]
