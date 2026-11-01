"""The profile composition and analyzer invocation the Graham execution adapters share."""

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import patch

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext, BaseAnalyzer
from investment_analysis_engine.data.instrument_profile import InstrumentKind, InstrumentProfile
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import fixture_instrument_profile
from investment_analysis_engine.strategies._shared.invocation import run_analyzer_with_profile

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
BOUNDARY = datetime(2026, 1, 2, tzinfo=UTC)


def _profile(ticker: str) -> InstrumentProfile:
    return fixture_instrument_profile(ticker, kind=InstrumentKind.ETF, provider_value="ETF", instrument_name="Fund")


@dataclass(frozen=True)
class _Analysis:
    ticker: str
    instrument_profile: InstrumentProfile | None


class _Analyzer(BaseAnalyzer[_Analysis, str]):
    def __init__(self, returned: InstrumentProfile | None) -> None:
        self.returned = returned
        self.calls: list[tuple[str, str, AnalysisContext]] = []

    def run_analysis(self, ticker: str, context: AnalysisContext, config: str) -> _Analysis:
        self.calls.append((ticker, config, context))
        return _Analysis(ticker=ticker, instrument_profile=self.returned)


def _run(analyzer: _Analyzer, composed: InstrumentProfile) -> tuple[_Analysis, InstrumentProfile, list[object]]:
    primary, yahoo = object(), object()
    with patch(
        "investment_analysis_engine.strategies._shared.invocation.compose_production_profile", return_value=composed
    ) as compose:
        analysis, profile = run_analyzer_with_profile(
            analyzer,
            "KO",
            "config",
            primary_provider=primary,
            profile_provider=yahoo,
            as_of=BOUNDARY,
            executed_at=NOW,
            use_cache=False,
            profile_cache=None,
        )
    forwarded = [compose.call_args.args, compose.call_args.kwargs, primary, yahoo]
    return analysis, profile, forwarded


def test_the_composed_profile_is_given_to_the_analyzer_and_kept_when_it_returns_none() -> None:
    composed = _profile("KO")
    analyzer = _Analyzer(None)

    analysis, profile, forwarded = _run(analyzer, composed)

    assert profile is composed
    assert analysis.ticker == "KO"
    ticker, config, context = analyzer.calls[0]
    assert (ticker, config) == ("KO", "config")
    assert (context.as_of, context.executed_at, context.use_cache) == (BOUNDARY, NOW, False)
    assert context.instrument_profile is composed
    assert forwarded[0] == ("KO",)
    assert forwarded[1] == {
        "primary_provider": forwarded[2],
        "yahoo_provider": forwarded[3],
        "profile_cache": None,
    }


def test_the_profile_the_analyzer_returns_replaces_the_composed_one() -> None:
    composed, completed = _profile("KO"), _profile("KO")
    analyzer = _Analyzer(completed)

    analysis, profile, _forwarded = _run(analyzer, composed)

    assert profile is completed
    assert analysis.instrument_profile is completed
    assert analyzer.calls[0][2].instrument_profile is composed
