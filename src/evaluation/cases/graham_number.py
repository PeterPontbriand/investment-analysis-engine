"""The reviewed Graham Number Golden-Suite cases and their production arguments."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from src.evaluation.fixtures.graham import (
    GOLDEN_HISTORICAL_AS_OF,
    GOLDEN_PRECEDENCE_EPS_OVERRIDE,
    GRAHAM_FACTS_FIXTURE_ID,
    GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID,
    NOW,
    SECURITY_ID,
)
from src.evaluation.fixtures.instrument_profiles import KNOWN_ETF_PROFILE_FIXTURE_ID
from src.evaluation.models import Case, DomainOutcomeExpectation, Expectation, NumericalExpectation, ToolConstraints
from src.orchestrator.tool_names import ToolName
from src.strategies.graham_number.tool import GrahamNumberToolArguments

_GRAHAM_NUMBER_TOOL_CONSTRAINTS: Final = ToolConstraints(
    permitted=(ToolName.ANALYZE_GRAHAM_NUMBER,),
    required=(ToolName.ANALYZE_GRAHAM_NUMBER,),
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
        tool_constraints=_GRAHAM_NUMBER_TOOL_CONSTRAINTS,
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
        tool_constraints=_GRAHAM_NUMBER_TOOL_CONSTRAINTS,
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


GRAHAM_NUMBER_CASES: Final[tuple[Case, ...]] = (GRN_01, GRN_02, GRA_ETF_01, GRN_03, GRN_04, GRN_05)

GRAHAM_NUMBER_ARGUMENTS: Final[Mapping[str, GrahamNumberToolArguments]] = MappingProxyType(
    {
        "GRN-01": GrahamNumberToolArguments(ticker=SECURITY_ID, eps_basis="three_year_average"),
        "GRN-02": GrahamNumberToolArguments(ticker=SECURITY_ID, eps_basis="ttm"),
        "GRA-ETF-01": GrahamNumberToolArguments(ticker="FLSW", eps_basis="three_year_average"),
        "GRN-03": GrahamNumberToolArguments(ticker="MISSING_QUOTE", eps_basis="three_year_average"),
        "GRN-04": GrahamNumberToolArguments(
            ticker=SECURITY_ID,
            as_of=NOW,
            eps_override=GOLDEN_PRECEDENCE_EPS_OVERRIDE,
        ),
        "GRN-05": GrahamNumberToolArguments(ticker=SECURITY_ID, as_of=GOLDEN_HISTORICAL_AS_OF),
    }
)
"""The reviewed production arguments of each Graham Number case, keyed by case id."""

__all__ = [
    "GRAHAM_NUMBER_ARGUMENTS",
    "GRAHAM_NUMBER_CASES",
    "GRA_ETF_01",
    "GRN_01",
    "GRN_02",
    "GRN_03",
    "GRN_04",
    "GRN_05",
]
