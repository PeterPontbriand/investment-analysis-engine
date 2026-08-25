"""Deterministic routing tests for composed production valuation providers."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.data.valuation.facts import ProviderFact, ValuationFactRequest, ValuationField
from src.data.valuation.production import ProductionValuationProvider
from src.data.valuation.provenance import ValuationSubjectKind
from src.data.yfinance import YFINANCE_PROVIDER_ID


@dataclass
class RecordingProvider:
    """Record valuation requests while returning explicit unavailability."""

    requests: list[ValuationFactRequest] = field(default_factory=list)

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Record one request and return no facts."""
        self.requests.append(request)
        return ()


def test_production_provider_routes_yfinance_quote_by_provider_identity() -> None:
    sec = RecordingProvider()
    massive = RecordingProvider()
    yfinance = RecordingProvider()
    provider = ProductionValuationProvider(sec_edgar=sec, massive=massive, yfinance=yfinance)
    request = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="KO",
        field_name=ValuationField.CURRENT_PRICE,
        provider_id=YFINANCE_PROVIDER_ID,
    )

    assert provider.fetch_facts(request) == ()
    assert yfinance.requests == [request]
    assert sec.requests == []
    assert massive.requests == []
