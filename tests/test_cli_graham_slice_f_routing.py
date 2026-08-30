"""Slice F CLI routing regressions for the explicit Massive Graham Number path."""

import pytest
import typer

from src.cli import GrahamCliMethod, _quote_provider_id, _validate_graham_options
from src.data.massive.constants import MASSIVE_PROVIDER_ID


def test_massive_number_requires_ttm_and_bvps_before_provider_work() -> None:
    """Unsupported Massive Number shapes are rejected at CLI validation."""
    with pytest.raises(typer.BadParameter, match="requires --eps-basis ttm"):
        _validate_graham_options(
            method=GrahamCliMethod.NUMBER,
            provider_id=MASSIVE_PROVIDER_ID,
            eps_basis="ttm",
            bvps=None,
            expected_growth=None,
            aaa_yield=None,
        )


def test_massive_ttm_number_with_bvps_uses_massive_quote() -> None:
    """The one supported Massive Number combination is explicit and deliberate."""
    basis = _validate_graham_options(
        method=GrahamCliMethod.NUMBER,
        provider_id=MASSIVE_PROVIDER_ID,
        eps_basis="ttm",
        bvps=42.0,
        expected_growth=None,
        aaa_yield=None,
    )

    assert basis == "ttm"
    assert _quote_provider_id(GrahamCliMethod.NUMBER, MASSIVE_PROVIDER_ID) == MASSIVE_PROVIDER_ID
