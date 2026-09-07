"""Typed analyzer for graham_number."""

from __future__ import annotations

from src.analysis.base_analyzer import BaseAnalyzer
from src.analysis.shared.graham_contracts import _resolve_ticker
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.graham_number.service import GrahamNumberAnalysis, run_graham_number_analysis
from src.data.instrument_profile import InstrumentProfile


class GrahamNumberAnalyzer(BaseAnalyzer[GrahamNumberConfig]):
    """Run the Number service with a borrowed resolver and optional fixed profile."""

    config_schema = GrahamNumberConfig

    def __init__(
        self,
        resolver: GrahamNumberInputResolver,
        *,
        default_ticker: str | None = None,
        instrument_profile: InstrumentProfile | None = None,
    ) -> None:
        """Borrow dependencies; composition owns their construction and closure."""
        super().__init__(default_ticker)
        self._resolver = resolver
        self._instrument_profile = instrument_profile

    def run_analysis(self, config: GrahamNumberConfig, ticker: str | None = None) -> GrahamNumberAnalysis:
        """Return complete service evidence for the explicit or default ticker."""
        selected = _resolve_ticker(ticker, self.default_ticker)
        assert config.eps_basis is not None
        assert config.quote_provider_id is not None
        return run_graham_number_analysis(
            resolver=self._resolver,
            ticker=selected,
            security_provider_id=config.security_provider_id,
            quote_provider_id=config.quote_provider_id,
            eps_basis=config.eps_basis,
            eps_override=config.eps_override,
            bvps_override=config.bvps_override,
            quote_override=config.quote_override,
            as_of=config.as_of,
            use_cache=config.use_cache,
            instrument_profile=self._instrument_profile,
        )
