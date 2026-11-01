"""The Piotroski analyzer over the captured statements: the real SEC adapter, resolver and provider, no network.

Only the transports are fixtures. A test may replace the Company Facts or the submissions document of an issuer, or its
filing header, to model another filing history.
"""

import copy
from datetime import UTC, datetime
from typing import Any

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.evaluation.fixtures.sec_edgar_statements import (
    HeaderFetcher,
    StatementsFetcher,
    captured_header,
    statements_adapter,
)
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiAnalyzer, PiotroskiResult

CLOCK = datetime(2026, 10, 25, 12, tzinfo=UTC)
HEADERS = {
    "aapl": "aapl_fy2024.hdr.sgml",
    "mnst": "mnst_fy2025.hdr.sgml",
    "jpm": "jpm_fy2025.hdr.sgml",
    "sap": "sap_fy2025.hdr.sgml",
    "ntr": "ntr_fy2025.hdr.sgml",
    "duk": "duk_fy2025.hdr.sgml",
}
"""The captured filing header of each issuer's anchor filing."""


def adapter_of(
    stem: str, *, fetcher: StatementsFetcher | None = None, header: HeaderFetcher | None = None
) -> SecEdgarFinancialFactsAdapter:
    """Return the real SEC adapter over the issuer's captured documents."""
    return statements_adapter(
        fetcher or StatementsFetcher(stem), header or HeaderFetcher(captured_header(HEADERS[stem])), clock_at=CLOCK
    )


def analyzer_of(adapter: SecEdgarFinancialFactsAdapter) -> PiotroskiAnalyzer:
    """Return the analyzer composed as production composes it: the adapter serves the resolver and the SIC code."""
    resolver = InputResolver(ProductionFinancialFactsProvider(sec_edgar=adapter), clock=lambda: CLOCK)
    return PiotroskiAnalyzer(resolver, adapter)


def run(
    stem: str,
    *,
    as_of: datetime | None = None,
    profile: InstrumentProfile | None = None,
    adapter: SecEdgarFinancialFactsAdapter | None = None,
) -> PiotroskiResult:
    """Run the analyzer for the issuer ``stem`` and return its result."""
    chosen = adapter or adapter_of(stem)
    context = AnalysisContext(as_of=as_of, executed_at=CLOCK, use_cache=True, instrument_profile=profile)
    return analyzer_of(chosen).run_analysis(stem.upper(), context)


def without_facts(stem: str, *, concepts: set[str], taxonomy: str = "us-gaap") -> StatementsFetcher:
    """Return the issuer's fetcher with every fact of the named concepts removed from its Company Facts."""
    fetcher = StatementsFetcher(stem)
    document = fetcher.documents["/companyfacts/"]
    assert isinstance(document, dict)
    facts: dict[str, Any] = copy.deepcopy(document)
    for concept in concepts:
        facts["facts"][taxonomy].pop(concept, None)
    fetcher.documents["/companyfacts/"] = facts
    return fetcher
