"""Deterministic routing tests for composed production financial-facts providers."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.data.financial.facts import FinancialFactRequest, FinancialField, ProviderFact
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.financial.provenance import FinancialSubjectKind
from src.data.yfinance import YFINANCE_PROVIDER_ID


@dataclass
class RecordingProvider:
    """Record financial-fact requests while returning explicit unavailability."""

    requests: list[FinancialFactRequest] = field(default_factory=list)

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        """Record one request and return no facts."""
        self.requests.append(request)
        return ()


def test_production_provider_routes_yfinance_quote_by_provider_identity() -> None:
    sec = RecordingProvider()
    massive = RecordingProvider()
    yfinance = RecordingProvider()
    provider = ProductionFinancialFactsProvider(sec_edgar=sec, massive=massive, yfinance=yfinance)
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="KO",
        field_name=FinancialField.CURRENT_PRICE,
        provider_id=YFINANCE_PROVIDER_ID,
    )

    assert provider.fetch_facts(request) == ()
    assert yfinance.requests == [request]
    assert sec.requests == []
    assert massive.requests == []
