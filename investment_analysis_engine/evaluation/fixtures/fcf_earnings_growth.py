"""Deterministic annual financial-fact fixtures for evaluation and tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from types import MappingProxyType
from typing import Final

import pandas as pd

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from investment_analysis_engine.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    FinancialSubjectKind,
    PeriodKind,
)
from investment_analysis_engine.data.market_data import (
    SPLIT_ADJUSTED_PRICE,
    MarketDataContext,
    SplitAdjustedHistory,
    SplitEvent,
)
from investment_analysis_engine.data.sec_edgar.cover_listing import (
    CoverListingRequest,
    CoverUnavailableReason,
    ListingEvidence,
    ListingResolution,
    SecurityKind,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEnd,
    AnchorYearEndRequest,
    AnchorYearEndResolution,
    AnchorYearEndUnavailableReason,
)
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID

FCF_GROWTH_SUCCESS_FIXTURE_ID: Final = "fcf_growth_success"
FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID: Final = "fcf_growth_nonmeaningful"
FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID: Final = "fcf_growth_period_as_of"

PROVIDER_ID = "annual-fixture"
RETRIEVED_AT = datetime(2026, 2, 1, tzinfo=UTC)

FCF_GROWTH_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
FCF_GROWTH_FCF_VALUES = (80.0, 90.0, 100.0, 110.0, 120.0, 130.0)
FCF_GROWTH_NONMEANINGFUL_FCF_VALUES = (80.0, 90.0, -5.0, 110.0, 120.0, 130.0)
FCF_GROWTH_EPS_VALUES = (2.0, 2.5, 3.0, 3.5, 4.0, 4.5)
FCF_GROWTH_CAPEX = 20.0
FCF_GROWTH_DILUTED_SHARES = 100.0
FCF_GROWTH_HISTORICAL_AS_OF = datetime(2025, 1, 15, tzinfo=UTC)
FCF_GROWTH_MISALIGNED_FISCAL_YEAR = 2023


class FixtureAnnualFinancialFactsProvider:
    """Return configured annual facts while recording deterministic calls."""

    def __init__(
        self,
        facts: tuple[ProviderFact, ...],
        *,
        error_field: FinancialField | None = None,
    ) -> None:
        """Initialize with immutable facts and an optional failing field."""
        self.facts = facts
        self.error_field = error_field
        self.requests: list[FinancialFactRequest] = []

    def fetch_facts(
        self,
        request: FinancialFactRequest,
        *,
        effective_as_of: datetime,  # noqa: ARG002
    ) -> tuple[ProviderFact, ...]:
        """Return matching configured facts or raise the configured error."""
        self.requests.append(request)
        if request.field_name is self.error_field:
            raise FinancialProviderError(
                "fixture provider failure", kind=ProviderFailureKind.UNREACHABLE, provider_id=request.provider_id
            )
        return tuple(
            fact
            for fact in self.facts
            if fact.field_name is request.field_name
            and fact.subject_id == request.subject_id
            and fact.provider_id == request.provider_id
        )


def annual_fact(  # noqa: PLR0913, PLR0917
    field: FinancialField,
    fiscal_year: int,
    value: float,
    *,
    available_at: datetime | None = None,
    provider_fact_id: str | None = None,
    currency: str = "USD",
    accounting_scope: AccountingScope | None = AccountingScope.CONSOLIDATED,
    period_kind: PeriodKind | None = PeriodKind.COMPLETED_ANNUAL,
    capex_sign: CapitalExpenditureSign | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> ProviderFact:
    """Build one completed annual fixture fact with exact-touching periods."""
    start = period_start or datetime(fiscal_year - 1, 1, 1, tzinfo=UTC)
    end = period_end or datetime(fiscal_year, 1, 1, tzinfo=UTC)
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ACME",
        field_name=field,
        value=value,
        units=(
            FinancialUnit.CURRENCY_PER_SHARE
            if field is FinancialField.EPS
            else FinancialUnit.SHARES
            if field is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES
            else FinancialUnit.CURRENCY
        ),
        provider_id=PROVIDER_ID,
        provider_field=f"fixture.{field.value}",
        retrieved_at=RETRIEVED_AT,
        basis="fiscal_year",
        currency=None if field is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES else currency,
        observation_period_start=start,
        observation_period_end=end,
        available_at=available_at or datetime(fiscal_year, 2, 1, tzinfo=UTC),
        fiscal_year=fiscal_year,
        period_kind=period_kind,
        accounting_scope=accounting_scope,
        capital_expenditure_sign=capex_sign,
        provider_fact_id=provider_fact_id or f"{field.value}-{fiscal_year}",
    )


def annual_series(
    years: range,
    *,
    fcf_values: tuple[float, ...] | None = None,
) -> tuple[ProviderFact, ...]:
    """Build compatible annual FCF, diluted-share, and diluted-EPS facts."""
    facts: list[ProviderFact] = []
    selected_years = tuple(years)
    for index, year in enumerate(selected_years):
        desired_fcf = fcf_values[index] if fcf_values is not None else 80.0 + index * 10.0
        capex = 20.0
        facts.extend(
            (
                annual_fact(
                    FinancialField.OPERATING_CASH_FLOW,
                    year,
                    desired_fcf + capex,
                    provider_fact_id=f"annual-{year}:operating_cash_flow",
                ),
                annual_fact(
                    FinancialField.CAPITAL_EXPENDITURES,
                    year,
                    capex,
                    capex_sign=CapitalExpenditureSign.POSITIVE_EXPENDITURE,
                    provider_fact_id=f"annual-{year}:capital_expenditures",
                ),
                annual_fact(
                    FinancialField.EPS,
                    year,
                    2.0 + index * 0.5,
                    provider_fact_id=f"annual-{year}:eps",
                ),
                annual_fact(
                    FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
                    year,
                    100.0,
                    provider_fact_id=f"annual-{year}:weighted_average_diluted_shares",
                ),
            )
        )
    return tuple(facts)


def fcf_growth_success_facts() -> tuple[ProviderFact, ...]:
    """Build the reviewed five-year positive-growth fixture evidence."""
    return annual_series(range(2020, 2026), fcf_values=FCF_GROWTH_FCF_VALUES)


def fcf_growth_nonmeaningful_facts() -> tuple[ProviderFact, ...]:
    """Build annual evidence containing an interior free-cash-flow sign change."""
    return annual_series(range(2020, 2026), fcf_values=FCF_GROWTH_NONMEANINGFUL_FCF_VALUES)


def fcf_growth_period_as_of_facts() -> tuple[ProviderFact, ...]:
    """Build evidence with one misaligned EPS period and a later unpublished year."""
    facts = fcf_growth_success_facts()
    return tuple(
        replace(
            fact,
            observation_period_start=datetime(2022, 1, 2, tzinfo=UTC),
        )
        if fact.field_name is FinancialField.EPS and fact.fiscal_year == FCF_GROWTH_MISALIGNED_FISCAL_YEAR
        else fact
        for fact in facts
    )


FCF_GROWTH_YEAR_END: Final = date(2025, 1, 1)
"""The fiscal year-end *t* of the success fixture: where its latest annual observation ends."""
FCF_GROWTH_FILING_DATE: Final = date(2025, 2, 1)
FCF_GROWTH_ACCESSION: Final = "0000000000-25-000001"
FCF_GROWTH_SHARE_COUNT: Final = 200.0
FCF_GROWTH_SPLIT: Final = SplitEvent(date(2025, 3, 3), 2.0)
"""A 2-for-1 split after the filing, so the count on the price's basis is 400 shares."""
FCF_GROWTH_PRICE: Final = 3.25
FCF_GROWTH_MARKET_CAP: Final = 1300.0
"""400 scaled shares at 3.25: the latest free cash flow of 130 is a yield of 10 percent."""

_FIXTURE_CIK = "0000000001"
_FIXTURE_COVER_URL = "https://www.sec.gov/Archives/edgar/data/1/000000000025000001/R1.htm"


def _share_count_fact(retrieved_at: datetime) -> ProviderFact:
    """Build the year-end share count the success fixture's anchor filing reports."""
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ACME",
        field_name=FinancialField.COMMON_SHARES_OUTSTANDING,
        value=FCF_GROWTH_SHARE_COUNT,
        units=FinancialUnit.SHARES,
        provider_id=SEC_PROVIDER_ID,
        provider_field="fixture.common_shares_outstanding",
        retrieved_at=retrieved_at,
        basis="fiscal_year_end",
        observation_period_end=datetime.combine(FCF_GROWTH_YEAR_END, time.min, tzinfo=UTC),
        available_at=datetime.combine(FCF_GROWTH_FILING_DATE, time.min, tzinfo=UTC),
        notes=(f"accession={FCF_GROWTH_ACCESSION}",),
    )


def _quote_fact(retrieved_at: datetime) -> ProviderFact:
    """Build the current quote of the success fixture."""
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="ACME",
        field_name=FinancialField.CURRENT_PRICE,
        value=FCF_GROWTH_PRICE,
        units=FinancialUnit.CURRENCY_PER_SHARE,
        provider_id=YFINANCE_PROVIDER_ID,
        provider_field="fixture.last_price",
        retrieved_at=retrieved_at,
        basis="latest_provider_quote",
        currency="USD",
    )


class FixtureMarketCapProvider:
    """Serve the success fixture's share count, quote, anchor year-end and cover without any network access.

    Without data it serves nothing: no fact, no anchor year-end and no cover, so a case that does not select the
    market-data fixture has an FCF yield that is unavailable and makes no request.
    """

    def __init__(self, retrieved_at: datetime, *, with_data: bool) -> None:
        """Retain the clock and whether the fixture holds the success fixture's market data."""
        self._retrieved_at = retrieved_at
        self._with_data = with_data
        self.requests: list[FinancialFactRequest] = []

    def fetch_facts(
        self,
        request: FinancialFactRequest,
        *,
        effective_as_of: datetime,  # noqa: ARG002
    ) -> tuple[ProviderFact, ...]:
        """Return the share count at the fiscal year-end or the quote, when the fixture holds them."""
        self.requests.append(request)
        if not self._with_data or request.subject_id != "ACME":
            return ()
        if request.field_name is FinancialField.COMMON_SHARES_OUTSTANDING and request.basis == "fiscal_year_end":
            return (_share_count_fact(self._retrieved_at),) if request.provider_id == SEC_PROVIDER_ID else ()
        if request.field_name is FinancialField.CURRENT_PRICE and request.provider_id == YFINANCE_PROVIDER_ID:
            return (_quote_fact(self._retrieved_at),)
        return ()

    def resolve_anchor_year_end(self, request: AnchorYearEndRequest) -> AnchorYearEndResolution:  # noqa: ARG002
        """Return the success fixture's anchor filing and fiscal year-end, or why there is none."""
        if not self._with_data:
            return AnchorYearEndResolution(
                reason=AnchorYearEndUnavailableReason.NO_ANALYSIS_SCOPE,
                message="The fixture holds no market data for this case.",
            )
        return AnchorYearEndResolution(
            anchor=AnchorYearEnd(
                year_end=FCF_GROWTH_YEAR_END,
                accession=FCF_GROWTH_ACCESSION,
                form="10-K",
                filing_date=FCF_GROWTH_FILING_DATE,
                filing_dates=MappingProxyType({FCF_GROWTH_ACCESSION: FCF_GROWTH_FILING_DATE}),
            )
        )

    def resolve_cover_listing(self, request: CoverListingRequest) -> ListingResolution:
        """Return the success fixture's cover, which registers the ticker as common stock, or why none was read."""
        if not self._with_data:
            return ListingResolution(reason=CoverUnavailableReason.COVER_MISSING)
        return ListingResolution(
            evidence=ListingEvidence(
                ticker=request.ticker,
                kind=SecurityKind.SHARE,
                title="Common Stock, $0.01 par value",
                cik=_FIXTURE_CIK,
                accession=FCF_GROWTH_ACCESSION,
                form="10-K",
                accepted_at=datetime.combine(FCF_GROWTH_FILING_DATE, time.min, tzinfo=UTC),
                source_url=_FIXTURE_COVER_URL,
                retrieved_at=self._retrieved_at,
            )
        )


class FixtureSplitHistoryProvider:
    """Serve the success fixture's split-adjusted history, adjusted on the day the live path asks for."""

    def __init__(self, retrieved_at: datetime, *, with_data: bool) -> None:
        """Retain the clock and whether the fixture holds the success fixture's split history."""
        self._retrieved_at = retrieved_at
        self._with_data = with_data
        self.use_cache_seen: list[bool] = []

    def fetch_split_adjusted_history(
        self,
        ticker: str,  # noqa: ARG002
        start_date: str,  # noqa: ARG002
        *,
        use_cache: bool,
        adjusted_on: date | None = None,
        as_of: date | None = None,
    ) -> SplitAdjustedHistory:
        """Return the fixture's closes and its one split, or raise the no-data failure of a case without them."""
        self.use_cache_seen.append(use_cache)
        if not self._with_data:
            raise DataFetchError(
                "fixture split history is not selected", kind=ProviderFailureKind.NO_DATA, provider_id="fixture_market"
            )
        day = as_of or adjusted_on or self._retrieved_at.date()
        frame = pd.DataFrame({"Close": [FCF_GROWTH_PRICE]}, index=pd.DatetimeIndex([day]))
        return SplitAdjustedHistory(
            close=frame,
            events=(FCF_GROWTH_SPLIT,),
            context=MarketDataContext(
                provider_id="fixture_market",
                observation_interval="1d",
                data_as_of=day,
                currency="USD",
                observation_count=1,
                price_adjustment=SPLIT_ADJUSTED_PRICE,
            ),
            adjustment_date=adjusted_on or day,
        )
