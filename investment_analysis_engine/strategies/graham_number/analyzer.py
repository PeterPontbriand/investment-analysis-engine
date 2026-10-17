"""Typed analyzer for graham_number."""

from __future__ import annotations

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext, BaseAnalyzer, require_ticker
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputResolver
from investment_analysis_engine.strategies.graham_number.config import GrahamNumberConfig
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis, run_graham_number_analysis


class GrahamNumberAnalyzer(BaseAnalyzer[GrahamNumberConfig, GrahamNumberAnalysis]):
    """Run the Number service with a borrowed resolver."""

    def __init__(self, resolver: GrahamNumberInputResolver) -> None:
        """Borrow the resolver; composition owns its construction and closure."""
        self._resolver = resolver

    def run_analysis(self, ticker: str, config: GrahamNumberConfig, context: AnalysisContext) -> GrahamNumberAnalysis:
        """Return complete service evidence for the given ticker."""
        assert config.quote_provider_id is not None
        return run_graham_number_analysis(
            resolver=self._resolver,
            ticker=require_ticker(ticker),
            security_provider_id=config.security_provider_id,
            quote_provider_id=config.quote_provider_id,
            eps_override=config.eps_override,
            bvps_override=config.bvps_override,
            quote_override=config.quote_override,
            as_of=context.as_of,
            effective_as_of=context.effective_as_of,
            use_cache=context.use_cache,
            instrument_profile=context.instrument_profile,
        )
