"""A Graham run without ``--as-of`` retains, and replays, the instant its analyzer was given."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest

from src.analysis.base_analyzer import AnalysisContext
from src.evaluation.fixtures.graham import NOW, PROVIDER_ID, SECURITY_ID, FixtureFinancialFactsProvider
from src.reporting.analysis_runs import project_run
from src.reporting.presentation import PresentationMode
from src.reporting.replay_inputs import ReplayOptions
from src.strategies.graham_growth.analyzer import GrahamGrowthAnalyzer
from src.strategies.graham_growth.calculation import GrahamGrowthCalculationPolicy, GrahamGrowthInputResolver
from src.strategies.graham_growth.config import GrahamGrowthConfig
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_number.analyzer import GrahamNumberAnalyzer
from src.strategies.graham_number.calculation import GrahamNumberInputResolver
from src.strategies.graham_number.config import GrahamNumberConfig
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategy_wiring import EVIDENCE_BY_KEY, REPLAYS_BY_KEY
from src.workspace.codecs import decode_evidence
from tests._wiring import encode_native
from tests.reporting.test_analysis_run_replay import _graham_run, _growth_run

LATER = NOW + timedelta(days=1)
POLICY = GrahamGrowthCalculationPolicy(base_pe=8.5, growth_multiplier=2.0, baseline_aaa_yield=4.4)


def _analyze(growth: bool) -> Any:
    """Run the analyzer with no boundary, an execution time of ``NOW`` and a resolver clock reading ``LATER``."""
    context = AnalysisContext(as_of=None, executed_at=NOW, use_cache=False, instrument_profile=None)
    if growth:
        config = GrahamGrowthConfig.model_validate(
            {"security_provider_id": PROVIDER_ID, "expected_growth": 5.0, "aaa_yield_override": 4.5}
        )
        resolver = GrahamGrowthInputResolver(FixtureFinancialFactsProvider(), clock=lambda: LATER)
        return GrahamGrowthAnalyzer(resolver, policy=POLICY).run_analysis(SECURITY_ID, config, context)
    number_config = GrahamNumberConfig.model_validate({"security_provider_id": PROVIDER_ID})
    number_resolver = GrahamNumberInputResolver(FixtureFinancialFactsProvider(), clock=lambda: LATER)
    return GrahamNumberAnalyzer(number_resolver).run_analysis(SECURITY_ID, number_config, context)


@pytest.mark.parametrize("growth", [False, True])
def test_the_evidence_holds_the_instant_the_analyzer_was_given(growth: bool) -> None:
    """With no boundary the effective instant is the execution time, not a later clock read."""
    analysis = _analyze(growth)
    assert analysis.as_of is None
    assert analysis.effective_as_of == NOW
    assert analysis.effective_as_of != LATER


@pytest.mark.parametrize("growth", [False, True])
def test_the_instant_survives_storage_and_replay(growth: bool) -> None:
    """The stored evidence decodes to the same instant, and the replayed document writes it."""
    analysis = _analyze(growth)
    run = _growth_run(analysis=analysis) if growth else _graham_run(analysis=analysis)
    decoded = decode_evidence(run, EVIDENCE_BY_KEY)
    assert isinstance(decoded, GrahamGrowthAnalysis | GrahamNumberAnalysis)
    assert decoded.effective_as_of == NOW
    text = project_run(run, ReplayOptions(mode=PresentationMode.JSON), codecs=EVIDENCE_BY_KEY, replays=REPLAYS_BY_KEY)
    document = json.loads(text)
    assert document["requested_as_of"] is None
    assert document["effective_as_of"] == NOW.isoformat()


@pytest.mark.parametrize("growth", [False, True])
def test_a_stored_boundary_must_equal_the_effective_instant(growth: bool) -> None:
    """Evidence that names a boundary and a different effective instant is corrupt and does not decode."""
    payload = dict(encode_native(_analyze(growth)))
    analysis = payload["analysis"]
    assert isinstance(analysis, dict)
    payload["analysis"] = {**analysis, "as_of": LATER.isoformat()}
    codec = EVIDENCE_BY_KEY[
        ("graham_growth_value", "graham_growth_value") if growth else ("graham_number", "graham_number")
    ]
    with pytest.raises(ValueError, match="effective_as_of"):
        codec.decode(payload, SECURITY_ID)
