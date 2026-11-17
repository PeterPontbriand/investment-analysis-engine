"""Every data provider a provider check can name has a name to show."""

from investment_analysis_engine.data.provider_checks import PROVIDER_CHECKS
from investment_analysis_engine.reporting.presentation import PROVIDER_DISPLAY_NAMES


def test_every_provider_check_identifier_has_a_display_name() -> None:
    assert [item.provider_id for item in PROVIDER_CHECKS if item.provider_id not in PROVIDER_DISPLAY_NAMES] == []
