"""The profile composition and analyzer invocation the Graham execution adapters share."""

from datetime import datetime
from typing import Protocol

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext, BaseAnalyzer
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.strategies._shared.profile import compose_production_profile


class ProfiledAnalysis(Protocol):
    """An analysis that may carry the profile its analyzer completed."""

    @property
    def instrument_profile(self) -> InstrumentProfile | None:
        """The profile the analyzer returned, or ``None`` when it left the composed profile as it was."""
        ...


def run_analyzer_with_profile[ConfigT, AnalysisT: ProfiledAnalysis](  # noqa: PLR0913
    analyzer: BaseAnalyzer[AnalysisT, ConfigT],
    ticker: str,
    config: ConfigT,
    *,
    primary_provider: object,
    profile_provider: object,
    as_of: datetime | None,
    executed_at: datetime,
    use_cache: bool,
    profile_cache: InstrumentProfileResolver | None,
) -> tuple[AnalysisT, InstrumentProfile]:
    """Compose the profile, run ``analyzer`` with it and return the analysis with its associated profile.

    The associated profile is the analyzer's own ``instrument_profile`` when it returned one, otherwise the profile
    composed before the calculation.

    Args:
        analyzer: A borrowed, already-built analyzer.
        ticker: The normalized target ticker.
        config: The analyzer's configuration.
        primary_provider: The security-fact provider, tried first for identity.
        profile_provider: The Yahoo-identity candidate source.
        as_of: The requested point-in-time boundary, or ``None``.
        executed_at: The run's own execution clock, read once by the caller.
        use_cache: Whether resolved-input caching is enabled for this run.
        profile_cache: When supplied, resolves the profile through the durable cache instead of composing live.

    Returns:
        The native analysis and its associated profile.
    """
    composed_profile = compose_production_profile(
        ticker, primary_provider=primary_provider, yahoo_provider=profile_provider, profile_cache=profile_cache
    )
    context = AnalysisContext(
        as_of=as_of, executed_at=executed_at, use_cache=use_cache, instrument_profile=composed_profile
    )
    analysis = analyzer.run_analysis(ticker, context, config)
    return analysis, analysis.instrument_profile or composed_profile
