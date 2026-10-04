"""Momentum's fixture composition and fixture-capability requirement for the evaluation tier."""

from __future__ import annotations

from typing import Final

from src.config import settings
from src.core.constants import ConfigKeys
from src.evaluation.fixture_context import FixtureContext, FixtureRequirement, selected_variant
from src.evaluation.fixture_ids import MOMENTUM_BOUNDARY_FIXTURE_ID, MOMENTUM_SUCCESS_FIXTURE_ID
from src.evaluation.fixtures.market_data import (
    FixtureMarketDataProvider,
    momentum_boundary_frame,
    momentum_success_frame,
)
from src.strategies.momentum.analyzer import MomentumAnalyzer
from src.strategies.momentum.tool import MomentumToolDependencies

MOMENTUM_FIXTURE_IDS: Final = frozenset({MOMENTUM_SUCCESS_FIXTURE_ID, MOMENTUM_BOUNDARY_FIXTURE_ID})
_LABEL: Final = "Momentum price"

REQUIREMENT: Final = FixtureRequirement(MOMENTUM_FIXTURE_IDS, _LABEL, etf_profile_exempt=False)
"""Momentum needs a selected price fixture; an ETF profile does not stand in for price history."""


def compose(context: FixtureContext) -> MomentumToolDependencies:
    """Build Momentum's dependencies from the selected price fixture."""
    fixture_id = selected_variant(context.fixture_ids, MOMENTUM_FIXTURE_IDS, label=_LABEL)
    momentum_frame = (
        momentum_success_frame()
        if fixture_id == MOMENTUM_SUCCESS_FIXTURE_ID
        else momentum_boundary_frame()
        if fixture_id == MOMENTUM_BOUNDARY_FIXTURE_ID
        else momentum_boundary_frame().iloc[0:0].copy()
    )
    return MomentumToolDependencies(
        analyzer=MomentumAnalyzer(
            market_data_provider=FixtureMarketDataProvider(momentum_frame),
            start_date=str(settings.get_analysis_settings()[ConfigKeys.DEFAULT_SECTION][ConfigKeys.START_DATE]),
        )
    )
