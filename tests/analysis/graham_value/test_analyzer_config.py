"""Contract matrix for method-specific Graham requests."""

from typing import Any

import pytest
from pydantic import ValidationError

from investment_analysis_engine.strategies.graham_growth.config import GrahamGrowthConfig
from investment_analysis_engine.strategies.graham_number.config import GrahamNumberConfig


@pytest.mark.parametrize("basis", [None, "three_year_average", "fiscal_year"])
def test_growth_basis_default(basis: str | None) -> None:
    config = GrahamGrowthConfig.model_validate({"eps_basis": basis, "expected_growth": 5.0, "aaa_yield_override": 4.5})
    assert config.eps_basis == (basis or "three_year_average")


@pytest.mark.parametrize("basis", [None, "three_year_average", "fiscal_year"])
def test_number_has_no_eps_basis_field(basis: str | None) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        GrahamNumberConfig.model_validate({"eps_basis": basis})
    assert "eps_basis" not in GrahamNumberConfig.model_fields


@pytest.mark.parametrize("config_type", [GrahamNumberConfig, GrahamGrowthConfig])
def test_normalization_frozen_and_roundtrip(config_type: type[GrahamNumberConfig] | type[GrahamGrowthConfig]) -> None:
    values: dict[str, Any] = {}
    if config_type is GrahamGrowthConfig:
        values.update(eps_basis=" FISCAL_YEAR ", expected_growth=5.0, aaa_yield_override=4.5)
    config = config_type.model_validate(values)
    if isinstance(config, GrahamGrowthConfig):
        assert config.eps_basis == "fiscal_year"
    assert config_type.model_validate_json(config.model_dump_json()) == config
    with pytest.raises(ValidationError, match="frozen"):
        config.eps_override = 1.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("eps_basis", " "),
        ("eps_basis", "annual"),
        ("eps_basis", "ttm"),
        ("eps_basis", 1),
        ("eps_override", "4.5"),
        ("quote_override", True),
        ("method", None),
        ("presentation_mode", None),
    ],
)
@pytest.mark.parametrize("growth", [False, True])
def test_invalid_common_fields(field: str, value: object, growth: bool) -> None:
    values: dict[str, Any] = {field: value}
    config_type: type[GrahamNumberConfig] | type[GrahamGrowthConfig] = GrahamNumberConfig
    if growth:
        config_type = GrahamGrowthConfig
        values.update(expected_growth=5.0, aaa_yield_override=4.5)
    with pytest.raises(ValidationError):
        config_type.model_validate(values)


@pytest.mark.parametrize("field", ["expected_growth", "aaa_yield_override"])
def test_growth_fields_required_and_number_rejects_them(field: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        GrahamNumberConfig.model_validate({field: None})
    values = {"expected_growth": 5.0, "aaa_yield_override": 4.5}
    del values[field]
    with pytest.raises(ValidationError, match="Field required"):
        GrahamGrowthConfig.model_validate(values)
    values[field] = None  # type: ignore[assignment]
    with pytest.raises(ValidationError):
        GrahamGrowthConfig.model_validate(values)


def test_number_field_rejected_by_growth_even_when_null() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        GrahamGrowthConfig.model_validate({"expected_growth": 5.0, "aaa_yield_override": 4.5, "bvps_override": None})


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_numeric_financial_validity_is_deferred(value: float) -> None:
    GrahamNumberConfig(eps_override=value, bvps_override=value, quote_override=value)
    GrahamGrowthConfig(expected_growth=value, aaa_yield_override=value, eps_override=value, quote_override=value)
