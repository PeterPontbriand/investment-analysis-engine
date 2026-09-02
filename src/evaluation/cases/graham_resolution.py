"""The reviewed Graham input-resolution Golden-Suite cases."""

from typing import Final

from src.evaluation.composition import GRAHAM_FACTS_FIXTURE_ID, GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID
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

_NUMBER_TOOL_CONSTRAINTS: Final = ToolConstraints(
    permitted=(ToolName.ANALYZE_GRAHAM_NUMBER,),
    required=(ToolName.ANALYZE_GRAHAM_NUMBER,),
)
_NUMBER_METHOD_CONSTRAINTS: Final = GrahamMethodConstraints(
    permitted=(GrahamMethod.GRAHAM_NUMBER,),
    required=(GrahamMethod.GRAHAM_NUMBER,),
)


GRN_04: Final = Case(
    case_id="GRN-04",
    description=(
        "Proves override, cache, and provider precedence without allowing lower-precedence values to alter the "
        "Graham Number result."
    ),
    task=(
        "Analyze SYNTH with Graham Number at as_of 2025-07-01T12:00:00Z using EPS override 5.00, cached BVPS "
        "20.00, and the provider current price."
    ),
    fixture_ids=(GRAHAM_FACTS_FIXTURE_ID, GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID),
    expectation=Expectation(
        tool_constraints=_NUMBER_TOOL_CONSTRAINTS,
        graham_method_constraints=_NUMBER_METHOD_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(
                field_path="result.maximum_indicated_price",
                expected_value=47.43416490252569,
                absolute_tolerance=1e-9,
            ),
            NumericalExpectation(
                field_path="margin_of_safety_percent",
                expected_value=-10.258081084537493,
                absolute_tolerance=1e-9,
            ),
        ),
    ),
    tags=("graham_number", "precedence", "resolution"),
)


GRN_05: Final = Case(
    case_id="GRN-05",
    description=(
        "Detects look-ahead bias at a historical as_of boundary and distinguishes unavailable evidence from zero "
        "or an invalid ticker."
    ),
    task="Analyze SYNTH with default Graham Number inputs at as_of 2024-08-01T12:00:00Z.",
    fixture_ids=(GRAHAM_FACTS_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_NUMBER_TOOL_CONSTRAINTS,
        graham_method_constraints=_NUMBER_METHOD_CONSTRAINTS,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="assembly.bvps", expected_value=None),
            DomainOutcomeExpectation(field_path="assembly.current_price", expected_value=None),
            DomainOutcomeExpectation(field_path="assembly.eps", expected_value=None),
            DomainOutcomeExpectation(field_path="assembly.status", expected_value="input_unavailable"),
            DomainOutcomeExpectation(field_path="margin_of_safety_percent", expected_value=None),
            DomainOutcomeExpectation(field_path="result.maximum_indicated_price", expected_value=None),
            DomainOutcomeExpectation(field_path="result.status", expected_value="input_unavailable"),
        ),
    ),
    tags=("as_of", "graham_number", "input_unavailable", "resolution"),
)


GRAHAM_RESOLUTION_CASES: Final[tuple[Case, ...]] = (GRN_04, GRN_05)

__all__ = ["GRAHAM_RESOLUTION_CASES", "GRN_04", "GRN_05"]
