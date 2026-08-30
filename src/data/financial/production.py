"""Composed production financial-facts provider."""

from __future__ import annotations

from collections.abc import Mapping

from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialFactsProvider,
    ProviderFact,
)
from src.data.massive.constants import MASSIVE_PROVIDER_ID
from src.data.massive.financial_facts import MassiveFinancialFactsAdapter
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter
from src.data.security_identity import SecurityIdentity, SecurityIdentityProvider, SecurityIdentityRequest
from src.data.yfinance import YFINANCE_PROVIDER_ID, YFinanceFinancialFactsAdapter


class ProductionFinancialFactsProvider:
    """Route financial-fact requests to narrowly verified production adapters.

    Routing is driven by ``request.provider_id``. The façade does not rewrite
    provider identity, which preserves exact provenance through the resolver.
    """

    def __init__(
        self,
        *,
        sec_edgar: FinancialFactsProvider | None = None,
        massive: FinancialFactsProvider | None = None,
        yfinance: FinancialFactsProvider | None = None,
    ) -> None:
        """Initialize with optional injected adapters for deterministic tests."""
        self._providers: Mapping[str, FinancialFactsProvider] = {
            SEC_PROVIDER_ID: sec_edgar or SecEdgarFinancialFactsAdapter(),
            MASSIVE_PROVIDER_ID: massive or MassiveFinancialFactsAdapter(),
            YFINANCE_PROVIDER_ID: yfinance or YFinanceFinancialFactsAdapter(),
        }

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        """Dispatch to the provider named by the request, or return unavailable."""
        provider = self._providers.get(request.provider_id)
        if provider is None:
            return ()
        return provider.fetch_facts(request)

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        """Route an optional identity request without widening numeric facts."""
        provider = self._providers.get(request.provider_id)
        if provider is None or not isinstance(provider, SecurityIdentityProvider):
            return None
        return provider.resolve_security_identity(request)
