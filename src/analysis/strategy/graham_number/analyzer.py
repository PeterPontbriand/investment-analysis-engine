"""Typed analyzer for graham_number."""

from __future__ import annotations

from src.analysis.base_analyzer import AnalysisContext, BaseAnalyzer, require_ticker
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis, run_graham_number_analysis


class GrahamNumberAnalyzer(BaseAnalyzer[GrahamNumberConfig, GrahamNumberAnalysis]):
    """Run the Number service with a borrowed resolver."""

    def __init__(self, resolver: GrahamNumberInputResolver) -> None:
        """Borrow the resolver; composition owns its construction and closure."""
        self._resolver = resolver

    def run_analysis(self, ticker: str, config: GrahamNumberConfig, context: AnalysisContext) -> GrahamNumberAnalysis:
        """Return complete service evidence for the given ticker."""
        assert config.eps_basis is not None
        assert config.quote_provider_id is not None
        return run_graham_number_analysis(
            resolver=self._resolver,
            ticker=require_ticker(ticker),
            security_provider_id=config.security_provider_id,
            quote_provider_id=config.quote_provider_id,
            eps_basis=config.eps_basis,
            eps_override=config.eps_override,
            bvps_override=config.bvps_override,
            quote_override=config.quote_override,
            as_of=context.as_of,
            use_cache=context.use_cache,
            instrument_profile=context.instrument_profile,
        )
