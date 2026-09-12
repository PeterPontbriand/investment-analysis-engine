"""Deterministic service equivalence and resource ownership for Graham wrappers."""

from dataclasses import asdict
from typing import Any, Literal, overload
from unittest.mock import patch

import pytest

from src.analysis.base_analyzer import BaseAnalyzer
from src.analysis.strategy.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_growth.service import run_graham_growth_analysis
from src.analysis.strategy.graham_number.analyzer import GrahamNumberAnalyzer
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.graham_number.service import run_graham_number_analysis
from src.core.analysis_status import CalculationStatus
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import FinancialFactRequest, ProviderFact
from src.data.instrument_profile import InstrumentKind, InstrumentKindEvidence, InstrumentProfile
from src.evaluation.fixtures.graham import (
    NOW,
    PROVIDER_ID,
    SECURITY_ID,
    SUBJECT_ERROR,
    SUBJECT_MISSING,
    FixtureFinancialFactsProvider,
)

POLICY = GrahamGrowthCalculationPolicy(base_pe=8.5, growth_multiplier=2.0, baseline_aaa_yield=4.4)


class OwnedProvider(FixtureFinancialFactsProvider):
    def __init__(self) -> None:
        """Initialize observable provider ownership."""
        super().__init__()
        self.calls = 0
        self.closed = False

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        assert not self.closed
        self.calls += 1
        return super().fetch_facts(request)

    def close(self) -> None:
        self.closed = True


class OwnedCache(InMemoryResolvedInputCache):
    def __init__(self) -> None:
        """Initialize observable cache ownership."""
        super().__init__()
        self.closed = False

    def close(self) -> None:
        self.closed = True


@overload
def _resolver(growth: Literal[True]) -> GrahamGrowthInputResolver: ...


@overload
def _resolver(growth: Literal[False]) -> GrahamNumberInputResolver: ...


@overload
def _resolver(growth: bool) -> GrahamNumberInputResolver | GrahamGrowthInputResolver: ...


def _resolver(growth: bool) -> GrahamNumberInputResolver | GrahamGrowthInputResolver:
    resolver_type = GrahamGrowthInputResolver if growth else GrahamNumberInputResolver
    return resolver_type(FixtureFinancialFactsProvider(), clock=lambda: NOW)


def _config(growth: bool, **values: Any) -> GrahamNumberConfig | GrahamGrowthConfig:
    fields = {"security_provider_id": PROVIDER_ID, "as_of": NOW, **values}
    if growth:
        return GrahamGrowthConfig.model_validate({"expected_growth": 5.0, "aaa_yield_override": 4.5, **fields})
    return GrahamNumberConfig.model_validate(fields)


def _analyzer(growth: bool, resolver: GrahamNumberInputResolver | GrahamGrowthInputResolver, **kwargs: Any) -> Any:
    if growth:
        assert isinstance(resolver, GrahamGrowthInputResolver)
        return GrahamGrowthAnalyzer(resolver, policy=POLICY, **kwargs)
    assert isinstance(resolver, GrahamNumberInputResolver)
    return GrahamNumberAnalyzer(resolver, **kwargs)


@pytest.mark.parametrize("growth", [False, True])
@pytest.mark.parametrize("ticker", [SECURITY_ID, SUBJECT_MISSING, SUBJECT_ERROR])
@pytest.mark.parametrize("values", [{}, {"eps_override": 4.0, "quote_override": 20.0, "use_cache": False}])
def test_complete_service_equivalence(growth: bool, ticker: str, values: dict[str, Any]) -> None:
    config = _config(growth, **values)
    analyzer = _analyzer(growth, _resolver(growth), default_ticker=f" {ticker.lower()} ")
    kwargs = config.model_dump()
    if growth:
        kwargs["policy"] = POLICY
    expected = (
        run_graham_growth_analysis(resolver=_resolver(True), ticker=ticker, **kwargs)
        if growth
        else run_graham_number_analysis(resolver=_resolver(False), ticker=ticker, **kwargs)
    )
    actual = analyzer.run_analysis(config)
    assert asdict(actual) == asdict(expected)
    assert isinstance(analyzer, BaseAnalyzer)
    assert analyzer.config_schema is type(config)
    if growth and values:
        assert actual.result.status is CalculationStatus.INPUT_UNAVAILABLE
        assert "override" in actual.result.reason
    elif ticker == SECURITY_ID:
        assert actual.result.status is CalculationStatus.OK
    else:
        assert actual.result.status is not CalculationStatus.OK


@pytest.mark.parametrize("growth", [False, True])
@pytest.mark.parametrize(
    ("default", "ticker", "expected"),
    [(None, " synth ", SECURITY_ID), ("other", "synth", SECURITY_ID), (" synth ", None, SECURITY_ID)],
)
def test_ticker_selection(growth: bool, default: str | None, ticker: str | None, expected: str) -> None:
    result = _analyzer(growth, _resolver(growth), default_ticker=default).run_analysis(_config(growth), ticker)
    assert result.ticker == expected


@pytest.mark.parametrize("growth", [False, True])
@pytest.mark.parametrize(("default", "ticker"), [(None, None), (" ", None), (SECURITY_ID, ""), (SECURITY_ID, " ")])
def test_missing_ticker_rejected(growth: bool, default: str | None, ticker: str | None) -> None:
    with pytest.raises(ValueError, match="ticker"):
        _analyzer(growth, _resolver(growth), default_ticker=default).run_analysis(_config(growth), ticker)


@pytest.mark.parametrize("growth", [False, True])
@pytest.mark.parametrize("etf", [False, True])
def test_profile_retention_and_mismatch(growth: bool, etf: bool) -> None:
    evidence = InstrumentKindEvidence(SECURITY_ID, InstrumentKind.ETF, "ETF", "yfinance", NOW) if etf else None
    profile = InstrumentProfile(SECURITY_ID, None, evidence, ())
    provider = OwnedProvider()
    resolver_type = GrahamGrowthInputResolver if growth else GrahamNumberInputResolver
    analyzer = _analyzer(growth, resolver_type(provider, clock=lambda: NOW), instrument_profile=profile)
    result = analyzer.run_analysis(_config(growth), SECURITY_ID)
    assert result.instrument_profile is not None
    assert result.instrument_profile.identity is profile.identity
    assert result.instrument_profile.kind_evidence is profile.kind_evidence
    if not etf:
        assert result.instrument_profile.security_unit_resolution is not None
        assert result.instrument_profile.security_unit_resolution.reason.value == "unsupported_temporal_evidence"
    if etf:
        assert result.result.status is CalculationStatus.NOT_APPLICABLE
        assert provider.calls == 0
    if growth:
        assert result.policy is POLICY
    with pytest.raises(ValueError, match="ticker"):
        analyzer.run_analysis(_config(growth), "OTHER")
    assert not provider.closed


@pytest.mark.parametrize("growth", [False, True])
def test_borrowed_resources_cache_reuse_and_bypass(growth: bool) -> None:
    provider, cache = OwnedProvider(), OwnedCache()
    resolver_type = GrahamGrowthInputResolver if growth else GrahamNumberInputResolver
    resolver = resolver_type(provider, cache=cache, clock=lambda: NOW)
    analyzer = _analyzer(growth, resolver)
    assert provider.calls == 0
    analyzer.run_analysis(_config(growth), SECURITY_ID)
    first_calls = provider.calls
    assert first_calls > 0
    analyzer.run_analysis(_config(growth), SECURITY_ID)
    assert provider.calls == first_calls
    analyzer.run_analysis(_config(growth, use_cache=False), SECURITY_ID)
    assert provider.calls > first_calls
    with (
        patch.object(
            resolver,
            "assemble_growth_value" if growth else "assemble_graham_number",
            side_effect=RuntimeError("failure"),
        ),
        pytest.raises(RuntimeError, match="failure"),
    ):
        analyzer.run_analysis(_config(growth), SECURITY_ID)
    assert not provider.closed
    assert not cache.closed


@pytest.mark.parametrize(
    ("growth", "field"),
    [
        (False, "eps_override"),
        (False, "bvps_override"),
        (False, "quote_override"),
        (True, "eps_override"),
        (True, "expected_growth"),
        (True, "aaa_yield_override"),
        (True, "quote_override"),
    ],
)
@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_numeric_edge_cases_match_service(growth: bool, field: str, value: float) -> None:
    config = _config(growth, **{field: value})
    kwargs = config.model_dump()
    if growth:
        kwargs["policy"] = POLICY
    expected = (
        run_graham_growth_analysis(resolver=_resolver(True), ticker=SECURITY_ID, **kwargs)
        if growth
        else run_graham_number_analysis(resolver=_resolver(False), ticker=SECURITY_ID, **kwargs)
    )
    actual = _analyzer(growth, _resolver(growth)).run_analysis(config, SECURITY_ID)
    assert asdict(actual) == asdict(expected)
    # Optional quote failures may leave a valid calculation, but never a margin.
    if field == "quote_override":
        assert actual.margin_of_safety_percent is None
    elif growth and field in ("expected_growth", "eps_override") and value in (0.0, -1.0):
        assert actual.result.status is CalculationStatus.OK
    else:
        assert actual.result.status is not CalculationStatus.OK
