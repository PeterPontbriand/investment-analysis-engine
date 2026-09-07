"""Typed analyzer for graham_growth."""

from __future__ import annotations

from src.analysis.base_analyzer import BaseAnalyzer
from src.analysis.shared.graham_contracts import _resolve_ticker
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis, run_graham_growth_analysis
from src.data.instrument_profile import InstrumentProfile


class GrahamGrowthAnalyzer(BaseAnalyzer[GrahamGrowthConfig]):
    """Run the growth service with an explicitly injected calculation policy."""

    config_schema = GrahamGrowthConfig

    def __init__(
        self,
        resolver: GrahamGrowthInputResolver,
        *,
        policy: GrahamGrowthCalculationPolicy,
        default_ticker: str | None = None,
        instrument_profile: InstrumentProfile | None = None,
    ) -> None:
        """Borrow policy and execution dependencies without production setup."""
        super().__init__(default_ticker)
        self._resolver = resolver
        self._policy = policy
        self._instrument_profile = instrument_profile

    def run_analysis(self, config: GrahamGrowthConfig, ticker: str | None = None) -> GrahamGrowthAnalysis:
        """Return complete service evidence, retaining the supplied policy/profile."""
        selected = _resolve_ticker(ticker, self.default_ticker)
        assert config.eps_basis is not None
        assert config.quote_provider_id is not None
        return run_graham_growth_analysis(
            resolver=self._resolver,
            ticker=selected,
            security_provider_id=config.security_provider_id,
            quote_provider_id=config.quote_provider_id,
            eps_basis=config.eps_basis,
            eps_override=config.eps_override,
            expected_growth=config.expected_growth,
            aaa_yield_override=config.aaa_yield_override,
            quote_override=config.quote_override,
            as_of=config.as_of,
            use_cache=config.use_cache,
            policy=self._policy,
            instrument_profile=self._instrument_profile,
        )
