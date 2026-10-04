"""The reviewed Graham growth-value Golden-Suite cases and their production arguments."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from src.evaluation.fixtures.graham import GRAHAM_FACTS_FIXTURE_ID, SECURITY_ID
from src.evaluation.fixtures.instrument_profiles import KNOWN_ETF_PROFILE_FIXTURE_ID
from src.evaluation.fixtures.sec_edgar_fpi import (
    SEC_FPI_ASML_FIXTURE_ID,
    SEC_FPI_NTR_FIXTURE_ID,
    SEC_FPI_NVO_FIXTURE_ID,
)
from src.evaluation.models import Case, DomainOutcomeExpectation, Expectation, NumericalExpectation, ToolConstraints
from src.orchestrator.tool_names import ToolName
from src.strategies.graham_growth.tool import GrahamGrowthValueToolArguments

_GROWTH_TOOL_CONSTRAINTS: Final = ToolConstraints(
    permitted=(ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,),
    required=(ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,),
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


FPI_01: Final = Case(
    case_id="FPI-01",
    description="Proves an exact US-GAAP diluted-EPS fact filed on Form 20-F reaches Graham growth valuation.",
    task="Evaluate ASML using the frozen US-GAAP Form 20-F diluted-EPS evidence.",
    fixture_ids=(SEC_FPI_ASML_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GROWTH_TOOL_CONSTRAINTS,
        domain_outcome_expectations=(DomainOutcomeExpectation(field_path="result.status", expected_value="ok"),),
    ),
    tags=("fpi", "sec_edgar", "us_gaap", "20_f"),
)


FPI_02: Final = Case(
    case_id="FPI-02",
    description="Proves an exact IFRS diluted-EPS duration fact reaches Graham growth valuation.",
    task="Evaluate NTR using the frozen exact IFRS annual diluted-EPS evidence.",
    fixture_ids=(SEC_FPI_NTR_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GROWTH_TOOL_CONSTRAINTS,
        domain_outcome_expectations=(DomainOutcomeExpectation(field_path="result.status", expected_value="ok"),),
    ),
    tags=("fpi", "ifrs", "sec_edgar", "exact_concept"),
)


FPI_04: Final = Case(
    case_id="FPI-04",
    description="Proves NVO ADR evidence cannot enable an unapproved filing-per-share/quote comparison.",
    task="Evaluate NVO without applying ADR or currency conversion to the quote comparison.",
    fixture_ids=(SEC_FPI_NVO_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GROWTH_TOOL_CONSTRAINTS,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="result.status", expected_value="ok"),
            DomainOutcomeExpectation(field_path="margin_of_safety_percent", expected_value=None),
        ),
    ),
    tags=("adr", "fpi", "security_unit_negative", "sec_edgar"),
)


GRAHAM_GROWTH_CASES: Final[tuple[Case, ...]] = (GRG_01, GRG_ETF_01, FPI_01, FPI_02, FPI_04)

GRAHAM_GROWTH_ARGUMENTS: Final[Mapping[str, GrahamGrowthValueToolArguments]] = MappingProxyType(
    {
        "GRG-01": GrahamGrowthValueToolArguments(
            ticker=SECURITY_ID,
            eps_basis="ttm",
            expected_growth=6.5,
            current_aaa_yield=4.15,
        ),
        "GRG-ETF-01": GrahamGrowthValueToolArguments(
            ticker="FLSW",
            eps_basis="ttm",
            expected_growth=6.5,
            current_aaa_yield=4.15,
        ),
        "FPI-01": GrahamGrowthValueToolArguments(
            ticker="ASML",
            eps_basis="fiscal_year",
            expected_growth=6.5,
            current_aaa_yield=4.15,
            current_price_override=None,
        ),
        "FPI-02": GrahamGrowthValueToolArguments(
            ticker="NTR",
            eps_basis="fiscal_year",
            expected_growth=6.5,
            current_aaa_yield=4.15,
            current_price_override=None,
        ),
        "FPI-04": GrahamGrowthValueToolArguments(
            ticker="NVO",
            eps_basis="fiscal_year",
            expected_growth=6.5,
            current_aaa_yield=4.15,
            current_price_override=100.0,
        ),
    }
)
"""The reviewed production arguments of each Graham growth-value case, keyed by case id."""


__all__ = [
    "FPI_01",
    "FPI_02",
    "FPI_04",
    "GRAHAM_GROWTH_ARGUMENTS",
    "GRAHAM_GROWTH_CASES",
    "GRG_01",
    "GRG_ETF_01",
]
