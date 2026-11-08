"""The registry of the shared code sets: the term table of each, and the code sets that name no term.

This is the one registry API.6b serves as ``GET /v1/help/references``. ``SHARED_CODE_TERMS`` names each shared OpenAPI
component and the table that gives every value of it a glossary term. It is written out like ``STRATEGIES`` and never
discovered: a code set added to the API is added here in the same change, and the conformance test fails until it is. A
strategy's own code sets are reached through its descriptor's ``code_terms``.
"""

from collections.abc import Iterable, Mapping
from typing import Final, Protocol

from investment_analysis_engine.analysis.run_models import RUN_OUTCOME_TERMS
from investment_analysis_engine.analysis.shared.applicability import INDUSTRY_CLASS_TERMS
from investment_analysis_engine.analysis.shared.financial_resolution import PRICE_COMPARISON_STATUS_TERMS
from investment_analysis_engine.analysis.shared.market_cap import SHARE_COUNT_BASIS_TERMS
from investment_analysis_engine.analysis.shared.split_adjustment import ADJUSTMENT_WINDOW_TERMS
from investment_analysis_engine.api.refresh_documents import REFRESH_EVENT_KIND_TERMS
from investment_analysis_engine.core.analysis_status import CALCULATION_STATUS_TERMS
from investment_analysis_engine.core.constants import TREND_STATUS_TERMS
from investment_analysis_engine.core.failure_codes import FAILURE_REASON_CODE_TERMS, FAILURE_STATUS_TERMS
from investment_analysis_engine.core.metric_result import METRIC_STATUS_TERMS, REASON_CODE_TERMS
from investment_analysis_engine.core.provider_check_element import PROVIDER_CHECK_VERDICT_TERMS
from investment_analysis_engine.core.provider_failure_kind import PROVIDER_FAILURE_KIND_TERMS
from investment_analysis_engine.data.financial.provenance import (
    ACCOUNTING_SCOPE_TERMS,
    CAPITAL_EXPENDITURE_SIGN_TERMS,
    PERIOD_KIND_TERMS,
    SOURCE_KIND_TERMS,
)
from investment_analysis_engine.data.financial.quote_freshness import QUOTE_FRESHNESS_STATUS_TERMS
from investment_analysis_engine.data.instrument_profile import INSTRUMENT_KIND_TERMS
from investment_analysis_engine.reporting.headline import CELL_STATUS_TERMS
from investment_analysis_engine.workspace_documents.runs_compare import HEADLINE_UNAVAILABLE_TERMS

SHARED_CODE_TERMS: Final[Mapping[str, Mapping[str, str]]] = {
    "AccountingScope": ACCOUNTING_SCOPE_TERMS,
    "AdjustmentWindow": ADJUSTMENT_WINDOW_TERMS,
    "CalculationStatus": CALCULATION_STATUS_TERMS,
    "CapitalExpenditureSign": CAPITAL_EXPENDITURE_SIGN_TERMS,
    "CellStatusValue": CELL_STATUS_TERMS,
    "FailureReasonCode": FAILURE_REASON_CODE_TERMS,
    "FailureStatus": FAILURE_STATUS_TERMS,
    "HeadlineUnavailable": HEADLINE_UNAVAILABLE_TERMS,
    "IndustryClass": INDUSTRY_CLASS_TERMS,
    "InstrumentKind": INSTRUMENT_KIND_TERMS,
    "MetricStatus": METRIC_STATUS_TERMS,
    "PeriodKind": PERIOD_KIND_TERMS,
    "PriceComparisonStatus": PRICE_COMPARISON_STATUS_TERMS,
    "ProviderCheckVerdict": PROVIDER_CHECK_VERDICT_TERMS,
    "ProviderFailureKind": PROVIDER_FAILURE_KIND_TERMS,
    "QuoteFreshnessStatus": QUOTE_FRESHNESS_STATUS_TERMS,
    "ReasonCode": REASON_CODE_TERMS,
    "RefreshEventKind": REFRESH_EVENT_KIND_TERMS,
    "RunOutcome": RUN_OUTCOME_TERMS,
    "ShareCountBasis": SHARE_COUNT_BASIS_TERMS,
    "SourceKind": SOURCE_KIND_TERMS,
    "TrendStatus": TREND_STATUS_TERMS,
}
"""The term table of each shared code set, by the name of the OpenAPI component that carries it."""

EXEMPT_CODE_SETS: Final[Mapping[str, str]] = {
    "schema_version": "A document's version number is a plain integer a client compares, not a code a person reads.",
    "headline cell kind": "A headline cell's kind says whether its value is a number or a text, which the value shows.",
    "replay text mode": "The mode names which of the engine's text renderings the text is; the text explains itself.",
    "method_id path parameter": "The method identifier in a path is the strategy's own; its term explains it.",
}
"""The four code sets and fields that name no glossary term, each with its reason."""

EXEMPT_LOCATIONS: Final[Mapping[str, str]] = {
    "CellKind": "headline cell kind",
    "TextPresentationMode": "replay text mode",
    "query:mode": "replay text mode",
    "path:method_id": "method_id path parameter",
}
"""Where an exempt enumeration sits in the OpenAPI description, by component name or ``<location>:<parameter>``.

``schema_version`` is a constant in every document, so it never appears as an enumeration; a test requires that.
"""


class HasCodeTerms(Protocol):
    """What the registry needs of a strategy descriptor: the term tables of its own code sets."""

    @property
    def code_terms(self) -> Mapping[str, Mapping[str, str]]:
        """The term table of each of the strategy's code sets, by component name."""
        ...


def code_terms_by_component(descriptors: Iterable[HasCodeTerms]) -> dict[str, dict[str, str]]:
    """Return the term table of every code set: the shared registry merged with each strategy's own tables.

    The keys are sorted by component name; within a table the values keep the order it declares them.

    Raises:
        ValueError: If two tables are declared for the same component; the message names it.
    """
    tables: dict[str, Mapping[str, str]] = dict(SHARED_CODE_TERMS)
    for descriptor in descriptors:
        for component, table in descriptor.code_terms.items():
            if component in tables:
                raise ValueError(f"The code set {component!r} has two term tables.")
            tables[component] = table
    return {component: dict(tables[component]) for component in sorted(tables)}
