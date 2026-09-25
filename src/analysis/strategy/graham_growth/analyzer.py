"""Typed analyzer for graham_growth."""

from __future__ import annotations

from src.analysis.base_analyzer import AnalysisContext, BaseAnalyzer
from src.analysis.shared.financial_resolution import require_ticker
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_growth.service import GrahamGrowthAnalysis, run_graham_growth_analysis


class GrahamGrowthAnalyzer(BaseAnalyzer[GrahamGrowthConfig, GrahamGrowthAnalysis]):
    """Run the growth service with an explicitly injected calculation policy."""

    def __init__(self, resolver: GrahamGrowthInputResolver, *, policy: GrahamGrowthCalculationPolicy) -> None:
        """Borrow policy and execution dependencies without production setup."""
        self._resolver = resolver
        self._policy = policy

    def run_analysis(self, ticker: str, config: GrahamGrowthConfig, context: AnalysisContext) -> GrahamGrowthAnalysis:
        """Return complete service evidence, retaining the supplied policy."""
        assert config.eps_basis is not None
        assert config.quote_provider_id is not None
        return run_graham_growth_analysis(
            resolver=self._resolver,
            ticker=require_ticker(ticker),
            security_provider_id=config.security_provider_id,
            quote_provider_id=config.quote_provider_id,
            eps_basis=config.eps_basis,
            eps_override=config.eps_override,
            expected_growth=config.expected_growth,
            aaa_yield_override=config.aaa_yield_override,
            quote_override=config.quote_override,
            as_of=context.as_of,
            use_cache=context.use_cache,
            policy=self._policy,
            instrument_profile=context.instrument_profile,
        )
