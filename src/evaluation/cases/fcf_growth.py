"""The reviewed FCF/Earnings Growth Golden-Suite cases and their production arguments."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from src.evaluation.fixtures.fcf_earnings_growth import (
    FCF_GROWTH_HISTORICAL_AS_OF,
    FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,
    FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,
    FCF_GROWTH_SUCCESS_FIXTURE_ID,
)
from src.evaluation.fixtures.instrument_profiles import KNOWN_ETF_PROFILE_FIXTURE_ID
from src.evaluation.fixtures.sec_edgar_fpi import SEC_FPI_SAP_FIXTURE_ID
from src.evaluation.models import Case, DomainOutcomeExpectation, Expectation, NumericalExpectation, ToolConstraints
from src.orchestrator.tool_names import ToolName
from src.strategies.fcf_growth.models import HistoricalHorizon
from src.strategies.fcf_growth.tool import FCFEarningsGrowthToolArguments

_FCF_TOOL_CONSTRAINTS: Final = ToolConstraints(
    permitted=(ToolName.ANALYZE_FCF_EARNINGS_GROWTH,),
    required=(ToolName.ANALYZE_FCF_EARNINGS_GROWTH,),
)


FCF_01: Final = Case(
    case_id="FCF-01",
    description=(
        "Proves aligned annual FCF and diluted-EPS growth, five elapsed years from six observations, and the "
        "distinct FCF/Earnings Growth strategy signal versus Momentum price-trend metrics."
    ),
    task="Analyze ACME's reviewed five-year historical FCF and diluted-EPS growth.",
    fixture_ids=(FCF_GROWTH_SUCCESS_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_FCF_TOOL_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(field_path="selected_horizon_years", expected_value=5.0, absolute_tolerance=0.0),
            NumericalExpectation(field_path="selected_observation_count", expected_value=6.0, absolute_tolerance=0.0),
            NumericalExpectation(
                field_path="fcf_cagr.value", expected_value=10.197228772148015, absolute_tolerance=1e-12
            ),
            NumericalExpectation(
                field_path="fcf_per_share_cagr.value",
                expected_value=10.197228772148015,
                absolute_tolerance=1e-12,
            ),
            NumericalExpectation(
                field_path="eps_cagr.value", expected_value=17.607902252467357, absolute_tolerance=1e-12
            ),
        ),
    ),
    tags=("fcf_earnings_growth", "momentum_discrimination", "positive_growth"),
)


FCF_02: Final = Case(
    case_id="FCF-02",
    description=(
        "Proves that an interior FCF sign change makes compound FCF growth nonmeaningful even when endpoints are "
        "positive."
    ),
    task="Analyze ACME's reviewed historical FCF and diluted-EPS growth with the interior FCF sign change.",
    fixture_ids=(FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_FCF_TOOL_CONSTRAINTS,
        numerical_expectations=(
            NumericalExpectation(field_path="selected_horizon_years", expected_value=5.0, absolute_tolerance=0.0),
            NumericalExpectation(field_path="selected_observation_count", expected_value=6.0, absolute_tolerance=0.0),
            NumericalExpectation(
                field_path="eps_cagr.value", expected_value=17.607902252467357, absolute_tolerance=1e-12
            ),
        ),
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="classification", expected_value="indeterminate"),
            DomainOutcomeExpectation(field_path="classification_reason_code", expected_value="sign_change"),
            DomainOutcomeExpectation(field_path="execution_status", expected_value="ok"),
            DomainOutcomeExpectation(field_path="fcf_cagr.reason_code", expected_value="sign_change"),
            DomainOutcomeExpectation(field_path="fcf_cagr.status", expected_value="unavailable"),
            DomainOutcomeExpectation(field_path="fcf_per_share_cagr.reason_code", expected_value="sign_change"),
            DomainOutcomeExpectation(field_path="fcf_per_share_cagr.status", expected_value="unavailable"),
            DomainOutcomeExpectation(
                field_path="trend_classification",
                expected_value="insufficient_or_nonmeaningful_growth",
            ),
        ),
    ),
    tags=("fcf_earnings_growth", "indeterminate", "sign_change"),
)


FCF_03: Final = Case(
    case_id="FCF-03",
    description=(
        "Proves strict period alignment and historical as_of look-ahead rejection when the requested four-year "
        "history is non-contiguous."
    ),
    task=(
        "Analyze ACME with a strict four-year FCF/Earnings Growth horizon at as_of "
        f"{FCF_GROWTH_HISTORICAL_AS_OF.isoformat()}."
    ),
    fixture_ids=(FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_FCF_TOOL_CONSTRAINTS,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="classification", expected_value="indeterminate"),
            DomainOutcomeExpectation(
                field_path="classification_reason_code",
                expected_value="non_contiguous_history",
            ),
            DomainOutcomeExpectation(field_path="execution_status", expected_value="input_unavailable"),
            DomainOutcomeExpectation(field_path="fcf_cagr.reason_code", expected_value="non_contiguous_history"),
            DomainOutcomeExpectation(field_path="fcf_cagr.status", expected_value="unavailable"),
            DomainOutcomeExpectation(
                field_path="fcf_per_share_cagr.reason_code",
                expected_value="non_contiguous_history",
            ),
            DomainOutcomeExpectation(field_path="fcf_per_share_cagr.status", expected_value="unavailable"),
            DomainOutcomeExpectation(field_path="selected_horizon_years", expected_value=None),
            DomainOutcomeExpectation(
                field_path="trend_classification",
                expected_value="insufficient_or_nonmeaningful_growth",
            ),
        ),
    ),
    tags=("as_of", "fcf_earnings_growth", "input_unavailable", "non_contiguous_history"),
)


FCF_ETF_01: Final = Case(
    case_id="FCF-ETF-01",
    description=(
        "Completes the provider-confirmed ETF applicability matrix for reported company FCF and diluted-EPS "
        "growth without requesting issuer facts or substituting an aggregate strategy."
    ),
    task="Analyze FLSW with reported company Free Cash Flow & Earnings Growth.",
    fixture_ids=(KNOWN_ETF_PROFILE_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_FCF_TOOL_CONSTRAINTS,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="classification", expected_value="indeterminate"),
            DomainOutcomeExpectation(
                field_path="classification_reason_code",
                expected_value="instrument_kind_not_applicable",
            ),
            DomainOutcomeExpectation(field_path="execution_status", expected_value="not_applicable"),
            DomainOutcomeExpectation(
                field_path="fcf_cagr.reason_code",
                expected_value="instrument_kind_not_applicable",
            ),
            DomainOutcomeExpectation(field_path="fcf_cagr.status", expected_value="not_applicable"),
            DomainOutcomeExpectation(
                field_path="fcf_per_share_cagr.reason_code",
                expected_value="instrument_kind_not_applicable",
            ),
            DomainOutcomeExpectation(field_path="fcf_per_share_cagr.status", expected_value="not_applicable"),
            DomainOutcomeExpectation(field_path="selected_horizon_years", expected_value=None),
            DomainOutcomeExpectation(
                field_path="trend_classification",
                expected_value="insufficient_or_nonmeaningful_growth",
            ),
        ),
    ),
    tags=("etf", "fcf_earnings_growth", "not_applicable"),
)


FPI_03: Final = Case(
    case_id="FPI-03",
    description="Proves SAP's broader combined investing concept does not substitute for exact physical-PP&E CapEx.",
    task="Evaluate SAP FCF growth without substituting its broader near-miss CapEx concept.",
    fixture_ids=(SEC_FPI_SAP_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_FCF_TOOL_CONSTRAINTS,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="execution_status", expected_value="input_unavailable"),
            DomainOutcomeExpectation(field_path="classification", expected_value="indeterminate"),
        ),
    ),
    tags=("fpi", "ifrs", "exact_concept_negative", "sec_edgar"),
)


FCF_GROWTH_CASES: Final[tuple[Case, ...]] = (FCF_01, FCF_02, FCF_03, FCF_ETF_01, FPI_03)

FCF_GROWTH_ARGUMENTS: Final[Mapping[str, FCFEarningsGrowthToolArguments]] = MappingProxyType(
    {
        "FCF-01": FCFEarningsGrowthToolArguments(
            ticker="ACME",
            historical_horizon=HistoricalHorizon.LONGEST_AVAILABLE,
            as_of=None,
        ),
        "FCF-02": FCFEarningsGrowthToolArguments(
            ticker="ACME",
            historical_horizon=HistoricalHorizon.LONGEST_AVAILABLE,
            as_of=None,
        ),
        "FCF-03": FCFEarningsGrowthToolArguments(
            ticker="ACME",
            historical_horizon=HistoricalHorizon.FOUR_YEARS,
            as_of=FCF_GROWTH_HISTORICAL_AS_OF,
        ),
        "FCF-ETF-01": FCFEarningsGrowthToolArguments(
            ticker="FLSW",
            historical_horizon=HistoricalHorizon.LONGEST_AVAILABLE,
            as_of=None,
        ),
        "FPI-03": FCFEarningsGrowthToolArguments(ticker="SAP", currency="EUR"),
    }
)
"""The reviewed production arguments of each FCF & Earnings Growth case, keyed by case id."""

__all__ = [
    "FCF_01",
    "FCF_02",
    "FCF_03",
    "FCF_ETF_01",
    "FCF_GROWTH_ARGUMENTS",
    "FCF_GROWTH_CASES",
    "FPI_03",
]
