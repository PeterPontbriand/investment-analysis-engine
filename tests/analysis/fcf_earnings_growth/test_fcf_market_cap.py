"""The FCF yield over the market capitalization at the boundary, through the real analyzer and fixture providers.

Every market-data provider here is a fixture, so no test reaches a live service.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from unittest.mock import patch

import pytest

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.analysis.shared.market_cap import ShareCountBasis
from investment_analysis_engine.cli_support import exit_code_of
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.cache import InMemoryResolvedInputCache
from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    ProviderFact,
)
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.instrument_profile import InstrumentKind
from investment_analysis_engine.data.market_data import SplitAdjustedHistory
from investment_analysis_engine.data.sec_edgar.cover_listing import CoverListingRequest, ListingResolution
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEndRequest,
    AnchorYearEndResolution,
    AnchorYearEndUnavailableReason,
)
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FCF_GROWTH_ACCESSION,
    FCF_GROWTH_FILING_DATE,
    FCF_GROWTH_MARKET_CAP,
    FCF_GROWTH_PRICE,
    FCF_GROWTH_SHARE_COUNT,
    FCF_GROWTH_SPLIT,
    FCF_GROWTH_YEAR_END,
    FixtureAnnualFinancialFactsProvider,
    FixtureMarketCapProvider,
    FixtureSplitHistoryProvider,
    annual_series,
)
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import (
    GOLDEN_ETF_TICKER,
    fixture_instrument_profile,
    fixture_known_etf_profile,
)
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer, MarketCapDependencies
from investment_analysis_engine.strategies.fcf_growth.execution import execute_fcf_growth, from_fcf_growth_capture
from investment_analysis_engine.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from investment_analysis_engine.strategies.fcf_growth.models import (
    FCFEarningsGrowthConfig,
    FCFEarningsGrowthPolicy,
    FCFEarningsGrowthResult,
)
from investment_analysis_engine.strategies.fcf_growth.presenter import render_fcf_earnings_growth
from tests._fcf_market_data import CLOCK

SECRET = "SECRET provider text that must never reach an investor"
CONFIG = FCFEarningsGrowthConfig(policy=FCFEarningsGrowthPolicy(), currency="USD")


class SpyProvider(FixtureMarketCapProvider):
    """The fixture provider that counts the year-end and cover requests."""

    def __init__(self, *, with_data: bool = True) -> None:
        """Retain the fixture clock and count nothing yet."""
        super().__init__(CLOCK, with_data=with_data)
        self.anchor_requests = 0
        self.cover_requests = 0

    def resolve_anchor_year_end(self, request: AnchorYearEndRequest) -> AnchorYearEndResolution:
        self.anchor_requests += 1
        return super().resolve_anchor_year_end(request)

    def resolve_cover_listing(self, request: CoverListingRequest) -> ListingResolution:
        self.cover_requests += 1
        return super().resolve_cover_listing(request)


class QuoteFailsProvider(SpyProvider):
    """A quote provider that fails with the secret text."""

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        if request.field_name is FinancialField.CURRENT_PRICE:
            raise FinancialProviderError(SECRET, kind=ProviderFailureKind.UNREACHABLE, provider_id="yfinance")
        return super().fetch_facts(request, effective_as_of=effective_as_of)


class SplitFailsProvider(FixtureSplitHistoryProvider):
    """A split-history provider that fails with the secret text."""

    def fetch_split_adjusted_history(
        self,
        ticker: str,  # noqa: ARG002
        start_date: str,  # noqa: ARG002
        *,
        use_cache: bool,  # noqa: ARG002
        adjusted_on: date | None = None,  # noqa: ARG002
        as_of: date | None = None,  # noqa: ARG002
    ) -> SplitAdjustedHistory:
        raise DataFetchError(SECRET, kind=ProviderFailureKind.RATE_LIMITED, provider_id="yfinance")


class ScopeFailsProvider(SpyProvider):
    """A provider whose analysis scope cannot open: the registrant has no annual report at all (case a)."""

    @contextmanager
    def analysis_scope(
        self,
        *,
        subject_id: str,  # noqa: ARG002
        provider_id: str,  # noqa: ARG002
        as_of: datetime | None,  # noqa: ARG002
    ) -> Iterator[None]:
        raise FinancialProviderError(SECRET, kind=ProviderFailureKind.NO_DATA, provider_id=SEC_PROVIDER_ID)
        yield


class AfterBoundaryProvider(SpyProvider):
    """A provider whose registrant filed every annual report after the boundary (case b)."""

    def resolve_anchor_year_end(self, request: AnchorYearEndRequest) -> AnchorYearEndResolution:  # noqa: ARG002
        self.anchor_requests += 1
        return AnchorYearEndResolution(
            reason=AnchorYearEndUnavailableReason.ACCEPTED_AFTER_BOUNDARY,
            message="The registrant's annual filings were all accepted after the boundary.",
        )


def _annual(years: range = range(2020, 2026)) -> ProductionAnnualGrowthSeriesResolver:
    facts = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in annual_series(years)
    )
    return ProductionAnnualGrowthSeriesResolver(FixtureAnnualFinancialFactsProvider(facts), clock=lambda: CLOCK)


def _dependencies(
    provider: SpyProvider, split: FixtureSplitHistoryProvider | None = None, *, resolver: InputResolver | None = None
) -> MarketCapDependencies:
    return MarketCapDependencies(
        resolver=resolver or InputResolver(provider, clock=lambda: CLOCK),
        split_history=split or FixtureSplitHistoryProvider(CLOCK, with_data=True),
        listing=provider,
    )


def _run(
    market_data: MarketCapDependencies,
    *,
    policy: FCFEarningsGrowthPolicy | None = None,
    years: range = range(2020, 2026),
    use_cache: bool = True,
    as_of: datetime | None = None,
) -> FCFEarningsGrowthResult:
    config = FCFEarningsGrowthConfig(policy=policy or FCFEarningsGrowthPolicy(), currency="USD")
    return FCFEarningsGrowthAnalyzer(_annual(years), market_data).run_analysis(
        "acme", config, AnalysisContext(as_of=as_of, executed_at=CLOCK, use_cache=use_cache)
    )


def _same_run(left: FCFEarningsGrowthResult, right: FCFEarningsGrowthResult) -> None:
    """Assert that everything but the yield and its evidence is equal."""
    assert replace(left, market_capitalization=None, fcf_yield=right.fcf_yield, warnings=right.warnings) == replace(
        right, market_capitalization=None
    )


def test_the_yield_is_the_latest_free_cash_flow_over_the_market_cap_at_the_year_end() -> None:
    result = _run(_dependencies(SpyProvider()))

    assert result.fcf_yield.status is MetricStatus.OK
    assert result.fcf_yield.value == pytest.approx(10.0)
    evidence = result.market_capitalization
    assert evidence is not None
    assert evidence.result.value == pytest.approx(FCF_GROWTH_MARKET_CAP)
    assert evidence.share_count is not None
    assert evidence.share_count.value == FCF_GROWTH_SHARE_COUNT
    assert evidence.share_count_basis is ShareCountBasis.YEAR_END
    assert evidence.share_count_date == FCF_GROWTH_YEAR_END
    assert evidence.share_count_filing_date == FCF_GROWTH_FILING_DATE
    assert evidence.scaled_share_count == FCF_GROWTH_SHARE_COUNT * FCF_GROWTH_SPLIT.ratio
    assert evidence.splits_applied == (FCF_GROWTH_SPLIT,)
    assert evidence.price == FCF_GROWTH_PRICE
    assert evidence.price_date == CLOCK.date()
    assert (evidence.form, evidence.filing_currency, evidence.quote_currency) == ("10-K", "USD", "USD")
    assert evidence.listing_check is not None
    assert evidence.listing_check.affirmed
    assert evidence.listing_check.accession == FCF_GROWTH_ACCESSION
    assert not [warning for warning in result.warnings if "FCF yield" in warning]
    assert result.provider_failure is None


def test_the_rest_of_the_analysis_does_not_depend_on_market_data() -> None:
    with_data = _run(_dependencies(SpyProvider()))
    without = _run(_dependencies(SpyProvider(with_data=False)))

    assert without.fcf_yield.status is MetricStatus.UNAVAILABLE
    assert without.fcf_yield.reason_code is ReasonCode.MISSING_FACT
    assert without.market_capitalization is None
    _same_run(with_data, without)


@pytest.mark.parametrize("etf", [False, True])
def test_no_market_data_is_requested_when_the_yield_is_not_wanted(etf: bool) -> None:
    provider = SpyProvider()
    split = FixtureSplitHistoryProvider(CLOCK, with_data=True)
    dependencies = _dependencies(provider, split)
    policy = FCFEarningsGrowthPolicy(include_fcf_yield=etf)
    if etf:
        profile = fixture_known_etf_profile()
        result = FCFEarningsGrowthAnalyzer(_annual(), dependencies).run_analysis(
            GOLDEN_ETF_TICKER,
            CONFIG,
            AnalysisContext(as_of=None, executed_at=CLOCK, use_cache=True, instrument_profile=profile),
        )
    else:
        result = _run(dependencies, policy=replace(policy, include_fcf_yield=False))
        assert result.fcf_yield.reason_code is ReasonCode.NOT_REQUESTED

    assert result.market_capitalization is None
    assert provider.requests == []
    assert provider.anchor_requests == provider.cover_requests == 0
    assert split.use_cache_seen == []


def test_no_market_data_is_requested_when_no_fiscal_year_was_resolved() -> None:
    provider = SpyProvider()
    split = FixtureSplitHistoryProvider(CLOCK, with_data=True)
    result = _run(_dependencies(provider, split), years=range(2024, 2026))

    assert result.execution_status is not CalculationStatus.OK
    assert result.fcf_yield.reason_code is ReasonCode.MISSING_FACT
    assert result.market_capitalization is None
    assert provider.anchor_requests == 0
    assert split.use_cache_seen == []


def test_an_observation_that_ends_before_the_year_end_gives_incompatible_period() -> None:
    provider = SpyProvider()
    split = FixtureSplitHistoryProvider(CLOCK, with_data=True)
    result = _run(_dependencies(provider, split), years=range(2019, 2025))

    assert result.annual_observations[-1].period_end.date() == date(2024, 1, 1)
    assert result.fcf_yield.status is MetricStatus.UNAVAILABLE
    assert result.fcf_yield.reason_code is ReasonCode.INCOMPATIBLE_PERIOD
    assert result.market_capitalization is None
    assert provider.anchor_requests == 1
    assert provider.cover_requests == 0
    assert split.use_cache_seen == []
    assert any("never computed from an older year" in warning for warning in result.warnings)
    assert result.execution_status is CalculationStatus.OK


def test_case_b_every_annual_report_after_the_boundary_is_not_available_as_of() -> None:
    provider = AfterBoundaryProvider()
    split = FixtureSplitHistoryProvider(CLOCK, with_data=True)
    result = _run(_dependencies(provider, split))

    assert result.fcf_yield.status is MetricStatus.UNAVAILABLE
    assert result.fcf_yield.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
    assert result.fcf_yield.reason == "The registrant's annual filings were all accepted after the boundary."
    assert split.use_cache_seen == []
    assert result.execution_status is CalculationStatus.OK


def test_a_year_end_the_adapter_cannot_give_is_missing_fact() -> None:
    result = _run(_dependencies(SpyProvider(with_data=False)))

    assert result.fcf_yield.reason_code is ReasonCode.MISSING_FACT


def _assert_failure_leaves_the_run_untouched(result: FCFEarningsGrowthResult, provider: str, kind: str) -> None:
    baseline = _run(_dependencies(SpyProvider(with_data=False)))

    assert result.fcf_yield.status is MetricStatus.UNAVAILABLE
    assert result.fcf_yield.reason_code is ReasonCode.PROVIDER_ERROR
    assert result.market_capitalization is None
    warnings = [warning for warning in result.warnings if warning.startswith("FCF yield is unavailable")]
    assert len(warnings) == 1
    assert provider in warnings[0]
    assert kind in warnings[0]
    document = render_fcf_earnings_growth(result, PresentationMode.JSON)
    assert SECRET not in document
    assert SECRET not in (result.fcf_yield.reason or "")
    assert SECRET not in " ".join(result.warnings)
    assert result.provider_failure is None
    assert result.execution_status is baseline.execution_status is CalculationStatus.OK
    assert result.classification is baseline.classification
    assert result.classification_reason_code is baseline.classification_reason_code
    _same_run(result, baseline)


def test_a_split_history_failure_makes_the_yield_unavailable_naming_the_provider_and_kind() -> None:
    result = _run(_dependencies(SpyProvider(), SplitFailsProvider(CLOCK, with_data=True)))

    _assert_failure_leaves_the_run_untouched(result, "yfinance", "rate_limited")


def test_a_quote_failure_makes_the_yield_unavailable_naming_the_provider_and_kind() -> None:
    result = _run(_dependencies(QuoteFailsProvider()))

    _assert_failure_leaves_the_run_untouched(result, "yfinance", "unreachable")


def test_case_a_a_scope_that_cannot_open_is_a_provider_failure_of_the_yield_only() -> None:
    result = _run(_dependencies(ScopeFailsProvider()))

    _assert_failure_leaves_the_run_untouched(result, SEC_PROVIDER_ID, "no_data")


def test_a_failure_gives_the_same_outcome_and_exit_code_and_fires_no_provider_check() -> None:
    profile = fixture_instrument_profile("ACME", kind=InstrumentKind.EQUITY, provider_value="EQUITY")

    def execute(dependencies: MarketCapDependencies) -> tuple[RunOutcome, int, object]:
        with patch(
            "investment_analysis_engine.strategies.fcf_growth.execution.compose_graham_profile", return_value=profile
        ):
            capture = execute_fcf_growth(
                _annual(),
                "ACME",
                config=CONFIG,
                as_of=None,
                executed_at=CLOCK,
                use_cache=True,
                provider=object(),
                market_data=dependencies,
            )
        execution = from_fcf_growth_capture(capture)
        return execution.outcome, exit_code_of(execution.outcome), execution.provider_failure

    failed = execute(_dependencies(SpyProvider(), SplitFailsProvider(CLOCK, with_data=True)))
    without = execute(_dependencies(SpyProvider(with_data=False)))

    assert failed == without == (RunOutcome.COMPLETED, 0, None)


def test_no_cache_reaches_the_quote_and_the_split_history() -> None:
    provider = SpyProvider()
    split = FixtureSplitHistoryProvider(CLOCK, with_data=True)
    resolver = InputResolver(provider, cache=InMemoryResolvedInputCache(clock=lambda: CLOCK), clock=lambda: CLOCK)
    dependencies = _dependencies(provider, split, resolver=resolver)

    _run(dependencies, use_cache=False)
    _run(dependencies, use_cache=False)
    quotes_uncached = [r for r in provider.requests if r.field_name is FinancialField.CURRENT_PRICE]
    assert len(quotes_uncached) == 2
    assert split.use_cache_seen == [False, False]

    _run(dependencies, use_cache=True)
    assert split.use_cache_seen == [False, False, True]


def test_the_cover_is_read_once_per_run() -> None:
    provider = SpyProvider()
    _run(_dependencies(provider))

    assert provider.cover_requests == 1
    assert provider.anchor_requests == 1


def test_a_boundary_is_passed_to_the_assembly_for_the_requested_day() -> None:
    split = FixtureSplitHistoryProvider(CLOCK, with_data=True)
    result = _run(_dependencies(SpyProvider(), split), as_of=datetime(2026, 9, 1, tzinfo=UTC))

    assert result.requested_as_of == datetime(2026, 9, 1, tzinfo=UTC)
    assert result.market_capitalization is not None
    assert result.market_capitalization.price_date == date(2026, 9, 1)
