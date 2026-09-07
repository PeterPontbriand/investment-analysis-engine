"""Slice F CLI routing regressions for the explicit Massive Graham Number path."""

import pytest
import typer

from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.cli_support import config_usage_errors
from src.data.massive.constants import MASSIVE_PROVIDER_ID


def test_massive_number_requires_ttm_and_bvps_before_provider_work() -> None:
    """Unsupported Massive Number shapes are rejected at CLI validation."""
    with pytest.raises(typer.BadParameter, match="requires --bvps"), config_usage_errors():
        GrahamNumberConfig(security_provider_id=MASSIVE_PROVIDER_ID, eps_basis="ttm")


def test_massive_ttm_number_with_bvps_uses_massive_quote() -> None:
    """The one supported Massive Number combination is explicit and deliberate."""
    config = GrahamNumberConfig(
        security_provider_id=MASSIVE_PROVIDER_ID,
        eps_basis="ttm",
        bvps_override=42.0,
    )

    assert config.eps_basis == "ttm"
    assert config.quote_provider_id == MASSIVE_PROVIDER_ID
