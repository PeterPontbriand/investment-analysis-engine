"""Composed production financial-facts provider."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime

from src.data.financial.facts import (
    AnalysisScopedFinancialFactsProvider,
    FinancialFactRequest,
    FinancialFactsProvider,
    ProviderFact,
)
from src.data.instrument_profile import InstrumentKindEvidence, InstrumentKindProvider, InstrumentKindRequest
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

    def analysis_scope(
        self,
        *,
        subject_id: str,
        provider_id: str,
        as_of: datetime | None,
    ) -> AbstractContextManager[None]:
        """Route an optional immutable analysis scope to the selected provider."""
        provider = self._providers.get(provider_id.strip().lower())
        if provider is None or not isinstance(provider, AnalysisScopedFinancialFactsProvider):
            return nullcontext()
        return provider.analysis_scope(subject_id=subject_id, provider_id=provider_id, as_of=as_of)

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        """Route an optional identity request without widening numeric facts."""
        provider = self._providers.get(request.provider_id)
        if provider is None or not isinstance(provider, SecurityIdentityProvider):
            return None
        return provider.resolve_security_identity(request)

    def resolve_instrument_kind(self, request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        """Route an optional kind request without widening numeric facts."""
        provider = self._providers.get(request.provider_id)
        if provider is None or not isinstance(provider, InstrumentKindProvider):
            return None
        return provider.resolve_instrument_kind(request)
