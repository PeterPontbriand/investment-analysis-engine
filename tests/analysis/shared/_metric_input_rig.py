"""Test rigs for the shared input assembly: the SEC adapter serving the captured fixtures, with stub market data.

The adapter, the production provider and the resolver are the real ones. Only the transports and the market-data side
(quotes and the split history) are stubs, so no test reaches a live service.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import (
    FactsNotAvailableAsOf,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    InstantSeriesFacts,
    InstantSeriesRequest,
    ProviderFact,
)
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, PeriodKind
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.market_data import (
    SPLIT_ADJUSTED_PRICE,
    MarketDataContext,
    SplitAdjustedHistory,
    SplitEvent,
)
from investment_analysis_engine.data.sec_edgar.cover_listing import CoverReaderPolicy
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter
from tests._sec_instants import NOW, FixtureFetcher

COVERS = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "cover_pages"
SPLITS = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "split_history"
LIVE_NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
"""The day of the captured split histories' adjustment, which a live run's quote must share."""

COVER_FIXTURES = {
    "DUK": "duk_fy2025",
    "DE": "de_fy2025",
    "GOOGL": "googl_fy2025",
    "HON": "hon_fy2025",
    "JPM": "jpm_fy2025",
    "MNST": "mnst_fy2025",
    "MRNA": "mrna_fy2025",
    "PLD": "pld_fy2025",
    "WMT": "wmt_fy2026",
}


def read_cover(name: str) -> str:
    """Return a captured trimmed cover."""
    return (COVERS / f"{name}.r1.htm").read_text(encoding="utf-8")


def captured_history(name: str) -> SplitAdjustedHistory:
    """Return a captured split history: ``nvda``, ``wmt`` or ``cbsh``."""
    document = json.loads((SPLITS / f"{name}.json").read_text(encoding="utf-8"))
    return synthetic_history(
        {date.fromisoformat(day): float(value) for day, value in document["close"]},
        events=tuple(SplitEvent(date.fromisoformat(day), ratio) for day, ratio in document["events"]),
        adjustment_date=date.fromisoformat(document["adjustment_date"]),
        currency=document["currency"],
    )


def synthetic_history(
    closes: Mapping[date, float],
    *,
    events: tuple[SplitEvent, ...] = (),
    adjustment_date: date = date(2026, 10, 26),
    currency: str | None = "USD",
) -> SplitAdjustedHistory:
    """Return a split-adjusted history built in a test from ``closes``."""
    frame = pd.DataFrame({"Close": list(closes.values())}, index=pd.DatetimeIndex(list(closes)))
    return SplitAdjustedHistory(
        close=frame,
        events=events,
        context=MarketDataContext(
            provider_id="yfinance",
            observation_interval="1d",
            data_as_of=frame.index[-1].date(),
            currency=currency,
            observation_count=len(frame),
            price_adjustment=SPLIT_ADJUSTED_PRICE,
        ),
        adjustment_date=adjustment_date,
    )


class SplitStub:
    """A dated split-history provider that serves one response and records every request."""

    def __init__(self, history: SplitAdjustedHistory | None = None, error: BaseException | None = None) -> None:
        self.history = history
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def fetch_split_adjusted_history(
        self,
        ticker: str,
        start_date: str,
        *,
        use_cache: bool,
        adjusted_on: date | None = None,
        as_of: date | None = None,
    ) -> SplitAdjustedHistory:
        """Record the request, then raise the configured error or return the response."""
        self.calls.append(
            {"ticker": ticker, "start": start_date, "use_cache": use_cache, "adjusted_on": adjusted_on, "as_of": as_of}
        )
        if self.error is not None:
            raise self.error
        assert self.history is not None
        return self.history


class FactsStub:
    """A financial-facts provider that answers from a table and records every request.

    ``counts`` maps a share-count basis to a (value, period end, accession) answer; ``quote`` is the current price.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        counts: Mapping[str, tuple[float, date, str | None]] | None = None,
        error_basis: str | None = None,
        quote: tuple[float, str, datetime] | None = None,
        annual: Mapping[FinancialField, Sequence[tuple[float, date, datetime]]] | None = None,
        not_available_as_of: str | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.counts = dict(counts or {})
        self.quote = quote
        self.annual = dict(annual or {})
        self.not_available_as_of = not_available_as_of
        self.error_basis = error_basis
        self.error = error
        self.requests: list[FinancialFactRequest] = []
        self.series_requests: list[InstantSeriesRequest] = []

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        """Record the request, then raise the configured error or answer from the table."""
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.error_basis is not None and request.basis == self.error_basis:
            raise unreachable()
        if self.not_available_as_of is not None:
            raise FactsNotAvailableAsOf(self.not_available_as_of)
        if request.field_name is FinancialField.CURRENT_PRICE:
            if self.quote is None:
                return ()
            price, currency, stamp = self.quote
            return (
                ProviderFact(
                    FinancialSubjectKind.SECURITY,
                    request.subject_id,
                    FinancialField.CURRENT_PRICE,
                    price,
                    FinancialUnit.CURRENCY_PER_SHARE,
                    request.provider_id,
                    "stub:last_price",
                    stamp,
                    currency=currency,
                    basis="latest_provider_quote",
                ),
            )
        if request.field_name is FinancialField.COMMON_SHARES_OUTSTANDING:
            answer = self.counts.get(request.basis or "")
            if answer is None:
                return ()
            value, day, accession = answer
            return (
                ProviderFact(
                    FinancialSubjectKind.SECURITY,
                    request.subject_id,
                    FinancialField.COMMON_SHARES_OUTSTANDING,
                    value,
                    FinancialUnit.SHARES,
                    request.provider_id,
                    "stub:shares",
                    NOW,
                    basis=request.basis,
                    observation_period_end=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
                    available_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
                    notes=() if accession is None else (f"accession={accession}",),
                ),
            )
        return tuple(
            ProviderFact(
                FinancialSubjectKind.SECURITY,
                request.subject_id,
                request.field_name,
                value,
                FinancialUnit.CURRENCY,
                request.provider_id,
                "stub:annual",
                NOW,
                basis=request.basis,
                currency="USD",
                observation_period_start=datetime.combine(
                    day.replace(year=day.year - 1), datetime.min.time(), tzinfo=UTC
                ),
                observation_period_end=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
                available_at=available,
                fiscal_year=day.year,
                period_kind=PeriodKind.COMPLETED_ANNUAL,
                provider_fact_id=f"stub:{request.field_name.value}:{day}:{available:%Y%m%d}:{value}",
            )
            for value, day, available in self.annual.get(request.field_name, ())
        )

    def fetch_instant_series(self, request: InstantSeriesRequest, *, effective_as_of: datetime) -> InstantSeriesFacts:  # noqa: ARG002
        """Record the request, then raise the configured error."""
        self.series_requests.append(request)
        if self.error is not None:
            raise self.error
        return InstantSeriesFacts()


class SpyProduction(ProductionFinancialFactsProvider):
    """The production provider that records the fact and series requests it routes."""

    def __init__(self, **providers: Any) -> None:
        super().__init__(**providers)
        self.fact_requests: list[FinancialFactRequest] = []
        self.series_requests: list[InstantSeriesRequest] = []

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        """Record, then route."""
        self.fact_requests.append(request)
        return super().fetch_facts(request, effective_as_of=effective_as_of)

    def fetch_instant_series(self, request: InstantSeriesRequest, *, effective_as_of: datetime) -> InstantSeriesFacts:
        """Record, then route."""
        self.series_requests.append(request)
        return super().fetch_instant_series(request, effective_as_of=effective_as_of)


@dataclass
class Rig:
    """The real adapter, production provider and resolver over a fixture, with the requests they made."""

    fetcher: FixtureFetcher
    cover_urls: list[str]
    production: SpyProduction
    resolver: InputResolver
    quotes: FactsStub = field(default_factory=FactsStub)


def rig(
    ticker: str,
    *,
    quotes: FactsStub | None = None,
    cover: str | BaseException | None = None,
    fetcher: FixtureFetcher | None = None,
    now: datetime = LIVE_NOW,
) -> Rig:
    """Return the rig of an issuer; its cover is the captured one unless ``cover`` is given."""
    chosen = fetcher or FixtureFetcher(ticker)
    urls: list[str] = []

    def serve_cover(
        url: str,
        *,
        headers: Mapping[str, str],  # noqa: ARG001
        policy: CoverReaderPolicy,  # noqa: ARG001
        not_found: ProviderFailureKind,
        provider_id: str,
    ) -> str:
        urls.append(url)
        if isinstance(cover, BaseException):
            raise cover
        if cover is not None:
            return cover
        if ticker not in COVER_FIXTURES:
            raise FinancialProviderError("no captured cover", kind=not_found, provider_id=provider_id)
        return read_cover(COVER_FIXTURES[ticker])

    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=chosen, clock=lambda: now, user_agent="Synthetic test", cover_fetcher=serve_cover
    )
    stub = quotes or FactsStub()
    production = SpyProduction(sec_edgar=adapter, yfinance=stub)
    return Rig(chosen, urls, production, InputResolver(production, clock=lambda: now), stub)


def unreachable(provider_id: str = SEC_PROVIDER_ID) -> FinancialProviderError:
    """Return a classified provider failure."""
    return FinancialProviderError("unreachable", kind=ProviderFailureKind.UNREACHABLE, provider_id=provider_id)


def fetch_error(provider_id: str = "yfinance") -> DataFetchError:
    """Return a classified market-data failure."""
    return DataFetchError("rate limited", kind=ProviderFailureKind.RATE_LIMITED, provider_id=provider_id)
