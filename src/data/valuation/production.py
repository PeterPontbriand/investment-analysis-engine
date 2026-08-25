"""Composed production valuation-facts provider."""

from __future__ import annotations

from collections.abc import Mapping

from src.data.massive.constants import MASSIVE_PROVIDER_ID
from src.data.massive.valuation import MassiveValuationAdapter
from src.data.sec_edgar.valuation import SEC_PROVIDER_ID, SecEdgarValuationAdapter
from src.data.valuation.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationFactsProvider,
)
from src.data.yfinance import YFINANCE_PROVIDER_ID, YFinanceValuationAdapter


class ProductionValuationProvider:
    """Route valuation requests to narrowly verified production adapters.

    Routing is driven by ``request.provider_id``. The façade does not rewrite
    provider identity, which preserves exact provenance through the resolver.
    """

    def __init__(
        self,
        *,
        sec_edgar: ValuationFactsProvider | None = None,
        massive: ValuationFactsProvider | None = None,
        yfinance: ValuationFactsProvider | None = None,
    ) -> None:
        """Initialize with optional injected adapters for deterministic tests."""
        self._providers: Mapping[str, ValuationFactsProvider] = {
            SEC_PROVIDER_ID: sec_edgar or SecEdgarValuationAdapter(),
            MASSIVE_PROVIDER_ID: massive or MassiveValuationAdapter(),
            YFINANCE_PROVIDER_ID: yfinance or YFinanceValuationAdapter(),
        }

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Dispatch to the provider named by the request, or return unavailable."""
        provider = self._providers.get(request.provider_id)
        if provider is None:
            return ()
        return provider.fetch_facts(request)
