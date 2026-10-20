"""The annual FCF fixture facts labelled the way the SEC EDGAR provider labels its answers.

The FCF resolver reads every annual field from SEC EDGAR, so the facts a test hands it must carry that provider id.
"""

from dataclasses import replace
from typing import Any

from investment_analysis_engine.data.financial.facts import ProviderFact
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import annual_fact, annual_series


def sec_annual_series(years: range, *, fcf_values: tuple[float, ...] | None = None) -> tuple[ProviderFact, ...]:
    """Return ``annual_series(years)`` with every fact labelled ``SEC_PROVIDER_ID``."""
    return tuple(replace(fact, provider_id=SEC_PROVIDER_ID) for fact in annual_series(years, fcf_values=fcf_values))


def sec_annual_fact(*arguments: Any, **keywords: Any) -> ProviderFact:
    """Return ``annual_fact(...)`` labelled ``SEC_PROVIDER_ID``."""
    return replace(annual_fact(*arguments, **keywords), provider_id=SEC_PROVIDER_ID)
