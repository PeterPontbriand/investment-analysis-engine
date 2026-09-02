"""Versioned Step 2.5A Golden cases for foreign-private-issuer evidence."""

from typing import Final

from src.evaluation.fixtures.sec_edgar_fpi import (
    SEC_FPI_ASML_FIXTURE_ID,
    SEC_FPI_NTR_FIXTURE_ID,
    SEC_FPI_NVO_FIXTURE_ID,
    SEC_FPI_SAP_FIXTURE_ID,
)
from src.evaluation.models import Case, DomainOutcomeExpectation, Expectation, ToolConstraints, ToolName

_GROWTH = ToolConstraints(
    permitted=(ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,),
    required=(ToolName.ANALYZE_GRAHAM_GROWTH_VALUE,),
)
_FCF = ToolConstraints(
    permitted=(ToolName.ANALYZE_FCF_EARNINGS_GROWTH,),
    required=(ToolName.ANALYZE_FCF_EARNINGS_GROWTH,),
)

FPI_01: Final = Case(
    case_id="FPI-01",
    description="Proves an exact US-GAAP diluted-EPS fact filed on Form 20-F reaches Graham growth valuation.",
    task="Evaluate ASML using the frozen US-GAAP Form 20-F diluted-EPS evidence.",
    fixture_ids=(SEC_FPI_ASML_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GROWTH,
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
        tool_constraints=_GROWTH,
        domain_outcome_expectations=(DomainOutcomeExpectation(field_path="result.status", expected_value="ok"),),
    ),
    tags=("fpi", "ifrs", "sec_edgar", "exact_concept"),
)

FPI_03: Final = Case(
    case_id="FPI-03",
    description="Proves SAP's broader combined investing concept does not substitute for exact physical-PP&E CapEx.",
    task="Evaluate SAP FCF growth without substituting its broader near-miss CapEx concept.",
    fixture_ids=(SEC_FPI_SAP_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_FCF,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="execution_status", expected_value="input_unavailable"),
            DomainOutcomeExpectation(field_path="classification", expected_value="indeterminate"),
        ),
    ),
    tags=("fpi", "ifrs", "exact_concept_negative", "sec_edgar"),
)

FPI_04: Final = Case(
    case_id="FPI-04",
    description="Proves NVO ADR evidence cannot enable an unapproved filing-per-share/quote comparison.",
    task="Evaluate NVO without applying ADR or currency conversion to the quote comparison.",
    fixture_ids=(SEC_FPI_NVO_FIXTURE_ID,),
    expectation=Expectation(
        tool_constraints=_GROWTH,
        domain_outcome_expectations=(
            DomainOutcomeExpectation(field_path="result.status", expected_value="ok"),
            DomainOutcomeExpectation(field_path="margin_of_safety_percent", expected_value=None),
        ),
    ),
    tags=("adr", "fpi", "security_unit_negative", "sec_edgar"),
)

SEC_EDGAR_FPI_CASES: Final[tuple[Case, ...]] = (FPI_01, FPI_02, FPI_03, FPI_04)

__all__ = ["FPI_01", "FPI_02", "FPI_03", "FPI_04", "SEC_EDGAR_FPI_CASES"]
