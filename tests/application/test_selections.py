"""Building a selection from its model's fields: defaults, as-of rules and errors that name fields."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.selections import as_of_boundary, build_selection
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.config.component_settings import clear_component_settings_cache, load_component_settings
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.fcf_growth.vocabulary import HistoricalHorizon
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.strategy_wiring import FCF_GROWTH, GRAHAM_GROWTH, GRAHAM_NUMBER, MOMENTUM, PIOTROSKI

CONTEXT = ApplicationContext(settings=ProjectSettings())
GROWTH = {"expected_growth": 5.0, "aaa_yield_override": 4.5}


def _rejection(
    method_id: str, fields: dict[str, object], context: ApplicationContext = CONTEXT
) -> ActionParameterError:
    with pytest.raises(ActionParameterError) as caught:
        build_selection(context, method_id, fields)
    return caught.value


def test_an_undeclared_method_is_rejected_under_its_parameter() -> None:
    error = _rejection("not_a_method", {})

    assert (str(error), error.parameters, error.rule) == (
        "method_id is not a declared method.",
        ("method_id",),
        "selection.undeclared_method",
    )


@pytest.mark.parametrize("fixed", ["analysis_id", "method_id", "config_schema_version"])
def test_the_fields_a_class_fixes_are_rejected_as_unknown(fixed: str) -> None:
    error = _rejection(PIOTROSKI.method_id, {fixed: "x"})

    assert str(error) == f"Invalid {fixed}: Extra inputs are not permitted"
    assert (error.parameters, error.rule) == ((fixed,), "pydantic.extra_forbidden")


def test_an_unknown_field_is_rejected_by_name() -> None:
    error = _rejection(PIOTROSKI.method_id, {"colour": "red"})

    assert (str(error), error.parameters, error.rule) == (
        "Invalid colour: Extra inputs are not permitted",
        ("colour",),
        "pydantic.extra_forbidden",
    )


def test_a_date_is_the_end_of_that_day_in_utc_and_a_timestamp_is_kept() -> None:
    assert as_of_boundary(None) is None
    assert as_of_boundary(date(2025, 12, 31)) == datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    moment = datetime(2025, 12, 31, 12, tzinfo=UTC)
    assert as_of_boundary(moment) == moment
    built = build_selection(CONTEXT, PIOTROSKI.method_id, {"as_of": date(2025, 1, 15)})
    assert built.as_of == datetime(2025, 1, 15, 23, 59, 59, 999999, tzinfo=UTC)


def test_a_timestamp_without_an_offset_is_rejected_under_as_of() -> None:
    error = _rejection(PIOTROSKI.method_id, {"as_of": datetime(2025, 1, 15, 12)})  # noqa: DTZ001 - the case under test

    assert str(error) == "Timestamp as_of values must include an explicit timezone offset."
    assert (error.parameters, error.rule) == (("as_of",), "selection.as_of_offset")
    assert error.named({"as_of": "--as-of"}).args == (
        "Timestamp --as-of values must include an explicit timezone offset.",
    )


def test_an_as_of_that_is_not_a_date_is_rejected_under_as_of() -> None:
    error = _rejection(PIOTROSKI.method_id, {"as_of": 5})

    assert (error.parameters, error.rule) == (("as_of",), "pydantic.date_type")


def test_omitted_momentum_fields_are_filled_from_the_settings_and_given_ones_are_kept(tmp_path: Path) -> None:
    folder = tmp_path / "config"
    (folder / "strategies").mkdir(parents=True)
    (folder / "strategies" / "momentum.toml").write_text("short_window = 7\nlong_window = 90\n", encoding="utf-8")
    clear_component_settings_cache()
    try:
        context = ApplicationContext(settings=ProjectSettings(config_dir=folder))
        filled = build_selection(context, MOMENTUM.method_id, {})
        given = build_selection(context, MOMENTUM.method_id, {"short_window": 3, "long_window": 11})
    finally:
        clear_component_settings_cache()

    assert isinstance(filled, MomentumSelection)
    assert isinstance(given, MomentumSelection)
    shipped = load_component_settings("momentum", MomentumSettings, folder)
    assert (filled.short_window, filled.long_window, filled.rsi_period) == (7, 90, shipped.rsi_period)
    assert (given.short_window, given.long_window, given.rsi_period) == (3, 11, shipped.rsi_period)


@pytest.mark.parametrize(
    ("fields", "message", "rule"),
    [
        (
            {"short_window": 0},
            "Invalid momentum window: short_window must be positive (received 0).",
            "momentum.short_window_not_positive",
        ),
        (
            {"long_window": -4},
            "Invalid momentum window: long_window must be positive (received -4).",
            "momentum.long_window_not_positive",
        ),
        (
            {"rsi_period": 0},
            "Invalid momentum period: rsi_period must be positive (received 0).",
            "momentum.rsi_period_not_positive",
        ),
        (
            {"short_window": 30, "long_window": 20},
            "Invalid momentum windows: short_window (30) must be smaller than long_window (20).",
            "momentum.window_order",
        ),
    ],
)
def test_momentum_rules_keep_a_rule_identifier_and_their_values(
    fields: dict[str, object], message: str, rule: str
) -> None:
    error = _rejection(MOMENTUM.method_id, fields)

    assert (str(error), error.rule) == (message, rule)
    assert error.named({name: f"--{name.replace('_', '-')}" for name in error.action_parameters}).args == (
        message.replace("short_window", "--short-window")
        .replace("long_window", "--long-window")
        .replace("rsi_period", "--rsi-period"),
    )


def test_the_arguments_of_a_rule_are_the_values_it_showed() -> None:
    error = _rejection(MOMENTUM.method_id, {"short_window": 30, "long_window": 20})

    assert error.arguments == {"short_window_value": 30, "long_window_value": 20}
    assert error.parameters == ("short_window", "long_window")


def test_a_missing_required_field_names_the_field() -> None:
    error = _rejection(GRAHAM_GROWTH.method_id, {"aaa_yield_override": 4.5})

    assert (str(error), error.rule, error.parameters) == (
        "expected_growth is required.",
        "pydantic.missing",
        ("expected_growth",),
    )


def test_a_built_in_error_keeps_its_type_and_its_text() -> None:
    error = _rejection(GRAHAM_GROWTH.method_id, {**GROWTH, "eps_basis": "calendar"})

    assert error.rule == "pydantic.literal_error"
    assert str(error).startswith("Invalid eps_basis: Input should be 'three_year_average' or 'fiscal_year'")
    assert error.arguments["pydantic_message"] == "Input should be 'three_year_average' or 'fiscal_year'"


def test_a_non_finite_override_names_its_field_and_rule() -> None:
    error = _rejection(GRAHAM_NUMBER.method_id, {"eps_override": float("inf")})

    assert (str(error), error.rule) == (
        "Invalid eps_override: Financial override must be a finite number.",
        "graham-number.override_not_finite",
    )


def test_graham_growth_defaults_its_eps_basis_in_the_model() -> None:
    built = build_selection(CONTEXT, GRAHAM_GROWTH.method_id, GROWTH)

    assert isinstance(built, GrahamGrowthSelection)
    assert built.eps_basis == "three_year_average"
    assert GrahamGrowthSelection.model_fields["eps_basis"].get_default() == "three_year_average"


def test_a_nested_field_error_names_the_field_by_its_dotted_name() -> None:
    error = _rejection(FCF_GROWTH.method_id, {"policy": {"historical_horizon": "ten_years"}})

    assert error.parameters == ("policy.historical_horizon",)
    assert str(error).startswith("Invalid policy.historical_horizon: ")
    assert error.named({"policy.historical_horizon": "--growth-years"}).args[0].startswith("Invalid --growth-years: ")


def test_a_nested_mapping_builds_the_nested_policy() -> None:
    built = build_selection(
        CONTEXT, FCF_GROWTH.method_id, {"policy": {"historical_horizon": HistoricalHorizon.FIVE_YEARS}}
    )

    assert isinstance(built, FCFGrowthSelection)
    assert built.policy.historical_horizon is HistoricalHorizon.FIVE_YEARS
    assert built.currency == "USD"


def test_a_currency_that_is_not_an_iso_code_is_rejected_under_its_field() -> None:
    error = _rejection(FCF_GROWTH.method_id, {"currency": "US"})

    assert (str(error), error.rule) == ("currency must be a three-letter ISO 4217 code.", "fcf-growth.currency_format")
    assert build_selection(CONTEXT, FCF_GROWTH.method_id, {"currency": " eur "}).currency == "EUR"  # type: ignore[union-attr]


def test_only_the_first_error_is_reported() -> None:
    error = _rejection(GRAHAM_NUMBER.method_id, {"eps_override": float("inf"), "bvps_override": float("nan")})

    assert error.parameters == ("eps_override",)
