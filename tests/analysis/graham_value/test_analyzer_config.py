"""Contract matrix for method-specific Graham requests."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_number.config import GrahamNumberConfig


@pytest.mark.parametrize("growth", [False, True])
@pytest.mark.parametrize("provider", ["sec_edgar", "massive", "injected"])
@pytest.mark.parametrize("basis", [None, "three_year_average", "ttm"])
@pytest.mark.parametrize("bvps", [None, 20.0])
def test_provider_basis_matrix(growth: bool, provider: str, basis: str | None, bvps: float | None) -> None:
    values: dict[str, Any] = {"security_provider_id": provider, "eps_basis": basis}
    config_type: type[GrahamNumberConfig] | type[GrahamGrowthConfig]
    if growth:
        config_type = GrahamGrowthConfig
        values.update(expected_growth=5.0, aaa_yield_override=4.5)
    else:
        config_type = GrahamNumberConfig
        values["bvps_override"] = bvps
    effective = basis or ("ttm" if growth and provider != "sec_edgar" else "three_year_average")
    invalid = (
        (provider == "sec_edgar" and effective != "three_year_average")
        or (provider == "massive" and effective != "ttm")
        or (not growth and provider == "massive" and bvps is None)
    )
    if invalid:
        with pytest.raises(ValidationError):
            config_type.model_validate(values)
    else:
        config = config_type.model_validate(values)
        assert config.eps_basis == effective
        assert config.quote_provider_id == ("yfinance" if provider == "sec_edgar" else provider)
        assert config.use_cache is True


@pytest.mark.parametrize("config_type", [GrahamNumberConfig, GrahamGrowthConfig])
def test_normalization_frozen_and_roundtrip(config_type: type[GrahamNumberConfig] | type[GrahamGrowthConfig]) -> None:
    values: dict[str, Any] = {
        "security_provider_id": " CUSTOM ",
        "quote_provider_id": " QUOTES ",
        "eps_basis": " TTM ",
        "as_of": datetime(2025, 1, 1, tzinfo=UTC),
        "use_cache": False,
    }
    if config_type is GrahamGrowthConfig:
        values.update(expected_growth=5.0, aaa_yield_override=4.5)
    config = config_type.model_validate(values)
    assert (config.security_provider_id, config.quote_provider_id, config.eps_basis) == ("custom", "quotes", "ttm")
    assert config.as_of == values["as_of"]
    assert config.use_cache is False
    assert config_type.model_validate_json(config.model_dump_json()) == config
    with pytest.raises(ValidationError, match="frozen"):
        config.use_cache = True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("security_provider_id", " "),
        ("security_provider_id", None),
        ("quote_provider_id", " "),
        ("eps_basis", " "),
        ("eps_basis", "annual"),
        ("eps_basis", 1),
        ("as_of", datetime(2025, 1, 1)),
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
