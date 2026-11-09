"""FCF Growth takes its yield at the anchor the shared rule finds, over the SEC adapter's reading of filings."""

from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import date, datetime

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.core.metric_result import MetricStatus
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEndRequest,
    AnchorYearEndResolution,
    SecEdgarFinancialFactsAdapter,
)
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FCF_GROWTH_ACCESSION,
    FixtureAnnualFinancialFactsProvider,
    FixtureMarketCapProvider,
    FixtureSplitHistoryProvider,
    annual_series,
)
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer, MarketCapDependencies
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.models import (
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
)
from tests._fcf_market_data import CLOCK
from tests._sec_instants import FixtureFetcher, load

_AMENDMENT = "0000000000-25-000002"


class _AdapterAnchorProvider(FixtureMarketCapProvider):
    """The success fixture's market data, with the anchor year-end read by the real SEC adapter."""

    def __init__(self, adapter: SecEdgarFinancialFactsAdapter) -> None:
        super().__init__(CLOCK, with_data=True)
        self._adapter = adapter

    def analysis_scope(
        self, *, subject_id: str, provider_id: str, as_of: datetime | None
    ) -> AbstractContextManager[None]:
        return self._adapter.analysis_scope(subject_id=subject_id, provider_id=provider_id, as_of=as_of)

    def resolve_anchor_year_end(self, request: AnchorYearEndRequest) -> AnchorYearEndResolution:
        return self._adapter.resolve_anchor_year_end(request)


def _submissions() -> dict[str, object]:
    """Return the filings: the 2024 and 2025 fiscal years' reports, and a refiling of 2024 accepted after 2025's."""
    rows = [
        ("0000000000-24-000001", "10-K", "2024-02-01", "2024-01-01", "2024-02-01T12:00:00.000Z"),
        (FCF_GROWTH_ACCESSION, "10-K", "2025-02-01", "2025-01-01", "2025-02-01T12:00:00.000Z"),
        (_AMENDMENT, "10-K/A", "2025-03-01", "2024-01-01", "2025-03-01T12:00:00.000Z"),
    ]
    accessions, forms, filed, reported, accepted = (list(column) for column in zip(*rows, strict=True))
    recent = {
        "accessionNumber": accessions,
        "form": forms,
        "filingDate": filed,
        "reportDate": reported,
        "acceptanceDateTime": accepted,
        "primaryDocument": [f"{accession}.htm" for accession in accessions],
    }
    return {"tickers": ["ACME"], "filings": {"recent": recent, "files": []}}


def _run() -> FCFEarningsGrowthResult:
    document = load("JPM")
    fetcher = FixtureFetcher("JPM", companyfacts=document["companyfacts"], submissions=_submissions())
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=fetcher,
        clock=lambda: CLOCK,
        user_agent="Synthetic test",
        ticker_overrides={"ACME": document["cik"]},
    )
    provider = _AdapterAnchorProvider(adapter)
    facts = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in annual_series(range(2020, 2026))
    )
    annual = ProductionAnnualGrowthSeriesResolver(FixtureAnnualFinancialFactsProvider(facts), clock=lambda: CLOCK)
    market_data = MarketCapDependencies(
        resolver=InputResolver(provider, clock=lambda: CLOCK),
        split_history=FixtureSplitHistoryProvider(CLOCK, with_data=True),
        listing=provider,
    )
    return FCFEarningsGrowthAnalyzer(annual, market_data).run_analysis(
        "acme",
        AnalysisContext(as_of=None, executed_at=CLOCK, use_cache=True),
        FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD"),
    )


def test_an_older_years_amendment_accepted_after_the_newest_report_does_not_move_the_yield_to_that_year() -> None:
    result = _run()

    assert result.anchor_filing is not None
    assert (result.anchor_filing.accession, result.anchor_filing.year_end) == (FCF_GROWTH_ACCESSION, date(2025, 1, 1))
    assert result.anchor_filing.stale is False
    assert result.fcf_yield.status is MetricStatus.OK
    assert result.fcf_yield.value == 10.0
    assert result.anchor_filing.accession != _AMENDMENT
