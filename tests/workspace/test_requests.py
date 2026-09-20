"""Focused tests for typed, immutable workspace analysis selections."""

import json
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from src.analysis.strategy.fcf_earnings_growth.models import (
    FCFClassificationBasis,
    FCFEarningsGrowthPolicy,
    ForwardPolicy,
    HistoricalHorizon,
)
from src.analysis.strategy.graham_growth.config import GrahamGrowthConfig
from src.analysis.strategy.graham_number.config import GrahamNumberConfig
from src.analysis.strategy.momentum.momentum_analyzer import MomentumConfig
from src.workspace.requests import (
    AnalysisRequest,
    AnalysisSelection,
    FCFGrowthSelection,
    FCFPolicySnapshot,
    GrahamGrowthSelection,
    GrahamNumberSelection,
    MomentumSelection,
    parse_selection,
)


@pytest.fixture(autouse=True)
def mock_settings_config(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Materialize deterministic configured-policy defaults for selection snapshots."""
    with monkeypatch.context() as ctx:
        ctx.setattr(
            "src.config.ProjectSettings.get_momentum_analysis",
            lambda self: {"window_sizes": {"short_window": 2, "long_window": 5}},  # noqa: ARG005
        )
        yield


def test_fixed_identifiers_and_schema_version() -> None:
    momentum = MomentumSelection.from_settings()
    assert momentum.analysis_id == "momentum"
    assert (momentum.method_id, momentum.config_schema_version) == ("sma_crossover", 1)

    graham = GrahamNumberSelection()
    assert graham.analysis_id == "graham"
    assert (graham.method_id, graham.config_schema_version) == ("graham_number", 1)


def test_momentum_defaults_materialized_from_configured_policy() -> None:
    selection = MomentumSelection.from_settings()
    assert (selection.short_window, selection.long_window, selection.rsi_period) == (2, 5, 14)

    config = selection.to_momentum_config()
    assert isinstance(config, MomentumConfig)
    assert (config.short_window, config.long_window, config.rsi_period) == (2, 5, 14)


def test_momentum_explicit_inputs_win_over_settings() -> None:
    selection = MomentumSelection.from_settings(short_window=3, rsi_period=9)
    assert (selection.short_window, selection.long_window, selection.rsi_period) == (3, 5, 9)


def test_momentum_snapshot_is_independent_of_caller_inputs() -> None:
    caller_values = {"short_window": 20, "long_window": 60}
    selection = MomentumSelection.model_validate(caller_values)
    caller_values.update(short_window=1, long_window=2)

    assert (selection.short_window, selection.long_window, selection.rsi_period) == (20, 60, 14)
    assert (selection.to_momentum_config().short_window, selection.to_momentum_config().long_window) == (20, 60)


def test_momentum_rejects_foreign_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        MomentumSelection.from_settings(as_of=None)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        MomentumSelection(expected_growth=5.0)  # type: ignore[call-arg]


def test_momentum_rejects_invalid_windows() -> None:
    for value in (0, -1):
        with pytest.raises(ValidationError):
            MomentumSelection(short_window=value, long_window=5)
        with pytest.raises(ValidationError):
            MomentumSelection(short_window=2, long_window=5, rsi_period=value)

    with pytest.raises(ValidationError, match="smaller than long_window"):
        MomentumSelection(short_window=5, long_window=5)
    with pytest.raises(ValidationError, match="smaller than long_window"):
        MomentumSelection.from_settings(short_window=10, long_window=2)


@pytest.mark.parametrize("field", ["short_window", "long_window", "rsi_period"])
def test_momentum_selection_is_frozen(field: str) -> None:
    selection = MomentumSelection.from_settings()
    with pytest.raises(ValidationError):
        setattr(selection, field, 1)


@pytest.mark.parametrize("provider", ["sec_edgar", "massive"])
def test_graham_defaults_resolve_like_analyzer_config(provider: str) -> None:
    selection = GrahamNumberSelection(security_provider_id=provider, bvps_override=20.0)
    config = selection.to_graham_number_config()

    assert isinstance(config, GrahamNumberConfig)
    expected_basis = "three_year_average" if provider == "sec_edgar" else "ttm"
    expected_quote = "yfinance" if provider == "sec_edgar" else provider
    assert (selection.eps_basis, selection.quote_provider_id) == (expected_basis, expected_quote)
    assert config.use_cache is True


def test_graham_number_defaults() -> None:
    selection = GrahamNumberSelection()
    assert (selection.security_provider_id, selection.quote_provider_id, selection.eps_basis) == (
        "sec_edgar",
        "yfinance",
        "three_year_average",
    )
    assert selection.use_cache is True


def test_graham_normalization_and_explicit_values() -> None:
    as_of = datetime(2025, 1, 1, tzinfo=UTC)
    selection = GrahamNumberSelection.model_validate(
        {
            "security_provider_id": " MASSIVE ",
            "quote_provider_id": " YFINANCE ",
            "eps_basis": " TTM ",
            "eps_override": 4.5,
            "bvps_override": 20.0,
            "quote_override": 100.0,
            "as_of": as_of,
            "use_cache": False,
        }
    )
    assert (selection.security_provider_id, selection.quote_provider_id) == ("massive", "yfinance")
    config = selection.to_graham_number_config()
    assert (config.eps_override, config.bvps_override, config.quote_override) == (4.5, 20.0, 100.0)
    assert config.as_of == as_of
    assert config.use_cache is False


def test_graham_snapshot_is_independent_of_caller_inputs() -> None:
    caller_values = {"security_provider_id": "massive", "bvps_override": 25.0}
    selection = GrahamNumberSelection.model_validate(caller_values)
    caller_values.update(security_provider_id="sec_edgar")

    assert selection.security_provider_id == "massive"
    assert selection.to_graham_number_config().security_provider_id == "massive"


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"security_provider_id": "sec_edgar", "eps_basis": "ttm"}, "three-year average"),
        ({"security_provider_id": "massive", "eps_basis": "three_year_average"}, "TTM"),
        ({"security_provider_id": "massive"}, "book value per share"),
        ({"eps_basis": "annual"}, "literal_error"),
    ],
)
def test_graham_rejects_incompatible_provider_combinations(values: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        GrahamNumberSelection(**values)


@pytest.mark.parametrize("field", ["expected_growth", "aaa_yield_override"])
def test_graham_rejects_foreign_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        GrahamNumberSelection(**{field: None})  # type: ignore[arg-type]


def test_graham_rejects_naive_as_of() -> None:
    with pytest.raises(ValidationError, match="timezone_aware"):
        GrahamNumberSelection(as_of=datetime(2025, 1, 1))


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_graham_numeric_financial_validity_is_deferred(value: float) -> None:
    selection = GrahamNumberSelection(eps_override=value, bvps_override=value, quote_override=value)
    assert (selection.eps_override, selection.bvps_override, selection.quote_override) == (value, value, value)


def test_graham_selection_is_frozen() -> None:
    selection = GrahamNumberSelection()
    with pytest.raises(ValidationError):
        selection.use_cache = False


@pytest.mark.parametrize("model", [MomentumSelection, GrahamNumberSelection])
@pytest.mark.parametrize(
    ("field", "value"),
    [("analysis_id", "wrong"), ("method_id", "wrong"), ("config_schema_version", 2)],
)
def test_identity_overrides_rejected(
    model: type[MomentumSelection] | type[GrahamNumberSelection], field: str, value: object
) -> None:
    values: dict[str, object] = {"short_window": 2, "long_window": 5} if model is MomentumSelection else {}
    values[field] = value
    with pytest.raises(ValidationError) as error:
        model.model_validate(values)
    assert [item["loc"] for item in error.value.errors()] == [(field,)]


@pytest.mark.parametrize("field", ["eps_override", "bvps_override", "quote_override"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_override_rejected(field: str, value: float) -> None:
    with pytest.raises(ValidationError, match="finite number"):
        GrahamNumberSelection.model_validate({field: value})


@pytest.mark.parametrize("field", ["security_provider_id", "quote_provider_id"])
@pytest.mark.parametrize("value", ["injected", "quotes", "", "   "])
def test_unsupported_providers_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError) as error:
        GrahamNumberSelection.model_validate({field: value})
    assert [item["loc"] for item in error.value.errors()] == [(field,)]


@pytest.mark.parametrize("field", ["short_window", "long_window", "rsi_period"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_window_reports_target_field(field: str, value: object) -> None:
    values: dict[str, object] = {"short_window": 2, "long_window": 5, "rsi_period": 14}
    values[field] = value
    with pytest.raises(ValidationError) as error:
        MomentumSelection.model_validate(values)
    assert [item["loc"] for item in error.value.errors()] == [(field,)]


def test_rsi_period_one_preserves_existing_config_semantics() -> None:
    selection = MomentumSelection(short_window=2, long_window=5, rsi_period=1)
    assert selection.to_momentum_config().rsi_period == 1


def test_settings_mutation_and_converted_config_cannot_change_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    selection = MomentumSelection.from_settings()
    monkeypatch.setattr(
        "src.config.ProjectSettings.get_momentum_analysis",
        lambda self: {"window_sizes": {"short_window": 10, "long_window": 30}},  # noqa: ARG005
    )
    assert MomentumSelection.from_settings().short_window == 10
    converted = selection.to_momentum_config()
    converted.short_window = 1
    assert selection.short_window == 2
    assert selection.to_momentum_config().short_window == 2


def test_round_trip_and_conversion_do_not_read_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    momentum = MomentumSelection.from_settings()
    graham = GrahamNumberSelection(as_of=datetime(2025, 1, 1, tzinfo=UTC))

    def forbidden_settings(_self: object) -> None:
        pytest.fail("Snapshot reconstruction must not read settings")

    monkeypatch.setattr("src.config.ProjectSettings.get_momentum_analysis", forbidden_settings)
    assert MomentumSelection.model_validate_json(momentum.model_dump_json()) == momentum
    assert GrahamNumberSelection.model_validate_json(graham.model_dump_json()) == graham
    assert momentum.to_momentum_config().short_window == 2
    assert graham.to_graham_number_config().as_of == graham.as_of
    assert MomentumSelection.from_settings(short_window=2, long_window=5) == momentum


@pytest.mark.parametrize("missing", ["expected_growth", "aaa_yield_override"])
def test_growth_requires_each_explicit_assumption(missing: str) -> None:
    values = {"expected_growth": 5.0, "aaa_yield_override": 4.5}
    del values[missing]
    with pytest.raises(ValidationError) as error:
        GrahamGrowthSelection.model_validate(values)
    assert [item["loc"] for item in error.value.errors()] == [(missing,)]


@pytest.mark.parametrize("provider", ["sec_edgar", "massive"])
@pytest.mark.parametrize("growth", [0.0, -5.0, 5.0])
def test_growth_conversion_preserves_assumptions(provider: str, growth: float) -> None:
    selection = GrahamGrowthSelection(security_provider_id=provider, expected_growth=growth, aaa_yield_override=0.0)
    expected_basis = "three_year_average" if provider == "sec_edgar" else "ttm"
    expected_quote = "yfinance" if provider == "sec_edgar" else "massive"
    expected = GrahamGrowthConfig(security_provider_id=provider, expected_growth=growth, aaa_yield_override=0.0)
    assert selection.to_graham_growth_config() == expected
    assert (selection.eps_basis, selection.quote_provider_id) == (expected_basis, expected_quote)


@pytest.mark.parametrize("field", ["bvps_override", "calculation_policy", "policy"])
def test_growth_rejects_number_and_calculation_policy_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        GrahamGrowthSelection.model_validate({"expected_growth": 5.0, "aaa_yield_override": 4.5, field: None})


@pytest.mark.parametrize("field", ["expected_growth", "aaa_yield_override", "eps_override", "quote_override"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_growth_nonfinite_values_rejected(field: str, value: float) -> None:
    values = {"expected_growth": 5.0, "aaa_yield_override": 4.5, field: value}
    with pytest.raises(ValidationError, match="finite number"):
        GrahamGrowthSelection.model_validate(values)


@pytest.mark.parametrize(
    "options",
    [
        {"security_provider_id": "injected"},
        {"quote_provider_id": "quotes"},
        {"security_provider_id": "sec_edgar", "eps_basis": "ttm"},
        {"security_provider_id": "massive", "eps_basis": "three_year_average"},
        {"as_of": datetime(2025, 1, 1)},
        {"use_cache": "false"},
        {"expected_growth": None},
        {"aaa_yield_override": "4.5"},
    ],
)
def test_growth_rejects_incompatible_options(options: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GrahamGrowthSelection.model_validate({"expected_growth": 5.0, "aaa_yield_override": 4.5, **options})


def test_growth_snapshot_is_independent_and_frozen() -> None:
    supplied = {"expected_growth": 5.0, "aaa_yield_override": 4.5}
    selection = GrahamGrowthSelection.model_validate(supplied)
    supplied["expected_growth"] = 99.0
    assert selection.to_graham_growth_config().expected_growth == 5.0
    with pytest.raises(ValidationError, match="frozen_instance"):
        selection.expected_growth = 99.0


def test_fcf_defaults_match_existing_policy() -> None:
    selection = FCFGrowthSelection()
    assert selection.to_fcf_policy() == FCFEarningsGrowthPolicy()
    assert (selection.currency, selection.provider_id, selection.as_of, selection.use_cache) == (
        "USD",
        "sec_edgar",
        None,
        True,
    )


@pytest.mark.parametrize("horizon", list(HistoricalHorizon))
@pytest.mark.parametrize("basis", list(FCFClassificationBasis))
@pytest.mark.parametrize("forward", list(ForwardPolicy))
def test_fcf_native_enum_strings_round_trip(
    horizon: HistoricalHorizon, basis: FCFClassificationBasis, forward: ForwardPolicy
) -> None:
    selection = FCFGrowthSelection.model_validate(
        {
            "policy": {
                "historical_horizon": horizon.value,
                "classification_basis": basis.value,
                "forward_policy": forward.value,
                "include_fcf_yield": False,
            }
        }
    )
    assert selection.to_fcf_policy() == FCFEarningsGrowthPolicy(horizon, basis, forward, False)
    assert FCFGrowthSelection.model_validate_json(selection.model_dump_json()) == selection


@pytest.mark.parametrize(
    "policy",
    [
        {"unknown": 1},
        {"historical_horizon": 3},
        {"classification_basis": "momentum"},
        {"forward_policy": "automatic"},
        {"include_fcf_yield": "false"},
    ],
)
def test_fcf_policy_rejects_invalid_nested_fields(policy: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        FCFGrowthSelection.model_validate({"policy": policy})


def test_fcf_normalizes_currency_provider_and_preserves_time() -> None:
    boundary = datetime(2025, 1, 1, tzinfo=UTC)
    selection = FCFGrowthSelection.model_validate(
        {"currency": " cad ", "provider_id": " SEC_EDGAR ", "as_of": boundary, "use_cache": False}
    )
    assert (selection.currency, selection.provider_id, selection.as_of, selection.use_cache) == (
        "CAD",
        "sec_edgar",
        boundary,
        False,
    )


@pytest.mark.parametrize(
    "values",
    [
        {"currency": ""},
        {"currency": "US"},
        {"currency": "123"},
        {"provider_id": "massive"},
        {"as_of": datetime(2025, 1, 1)},
        {"use_cache": "false"},
        {"config": {}},
    ],
)
def test_fcf_rejects_invalid_request_options(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        FCFGrowthSelection.model_validate(values)


def test_fcf_policy_copies_input_and_converts_independently() -> None:
    caller_policy = {"historical_horizon": "3"}
    selection = FCFGrowthSelection.model_validate({"policy": caller_policy})
    caller_policy["historical_horizon"] = "5"
    assert selection.policy.historical_horizon is HistoricalHorizon.THREE_YEARS
    with pytest.raises(ValidationError, match="frozen_instance"):
        selection.policy.include_fcf_yield = False
    policy = FCFEarningsGrowthPolicy(historical_horizon=HistoricalHorizon.FOUR_YEARS)
    snapshot = FCFPolicySnapshot.model_validate(policy)
    assert snapshot.to_policy() == policy
    assert snapshot.to_policy() is not policy
    assert selection.to_fcf_policy() is not selection.to_fcf_policy()


@pytest.fixture
def all_selections() -> tuple[AnalysisSelection, ...]:
    return (
        MomentumSelection.from_settings(),
        GrahamNumberSelection(),
        FCFGrowthSelection(),
        GrahamGrowthSelection(expected_growth=5.0, aaa_yield_override=4.5),
    )


def test_all_request_variants_round_trip_without_settings(
    all_selections: tuple[AnalysisSelection, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_settings(_self: object) -> None:
        pytest.fail("Request replay must not read settings")

    monkeypatch.setattr("src.config.ProjectSettings.get_momentum_analysis", forbidden_settings)
    for selection in all_selections:
        request = AnalysisRequest(ticker=" cnr.to ", selection=selection)
        assert request.ticker == "CNR.TO"
        restored = AnalysisRequest.model_validate_json(request.model_dump_json())
        assert restored == request
        assert type(restored.selection) is type(selection)
        with pytest.raises(ValidationError, match="frozen_instance"):
            request.ticker = "KO"


@pytest.mark.parametrize("ticker", ["", "  "])
def test_request_rejects_empty_ticker(ticker: str) -> None:
    with pytest.raises(ValidationError, match="ticker must not be empty"):
        AnalysisRequest(ticker=ticker, selection=GrahamNumberSelection())


@pytest.mark.parametrize("field", ["as_of", "use_cache"])
def test_request_rejects_duplicated_method_options(field: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AnalysisRequest.model_validate({"ticker": "KO", "selection": GrahamNumberSelection(), field: None})


def test_union_rejects_bad_identifiers_and_versions(all_selections: tuple[AnalysisSelection, ...]) -> None:
    for selection in all_selections:
        for field, invalid in [("analysis_id", "wrong"), ("method_id", "wrong"), ("config_schema_version", 2)]:
            payload = selection.model_dump()
            payload[field] = invalid
            with pytest.raises(ValidationError):
                AnalysisRequest.model_validate({"ticker": "KO", "selection": payload})


@pytest.mark.parametrize(
    ("alias", "body", "analysis", "method"),
    [
        ("momentum", "{}", "momentum", "sma_crossover"),
        ("graham-number", "{}", "graham", "graham_number"),
        ("graham-growth", '{"config":{"expected_growth":5,"aaa_yield_override":4.5}}', "graham", "graham_growth_value"),
        ("fcf-growth", "{}", "fcf_earnings_growth", "reported_fcf_eps_cagr"),
    ],
)
def test_parser_aliases_and_canonical_identifiers(alias: str, body: str, analysis: str, method: str) -> None:
    selection = parse_selection(alias, body)
    assert (selection.analysis_id, selection.method_id, selection.config_schema_version) == (analysis, method, 1)


@pytest.mark.parametrize("alias", ["", "Momentum", " momentum", "graham_number", "sma_crossover", "fcf"])
def test_parser_rejects_nonexact_aliases(alias: str) -> None:
    with pytest.raises(ValueError, match="Unknown analysis alias"):
        parse_selection(alias, "{}")


@pytest.mark.parametrize("alias", ["momentum", "graham-number", "graham-growth", "fcf-growth"])
@pytest.mark.parametrize("body", ["", "{", '{"config":}', "{} trailing", '{"config":{},}', "[]", "null", "5", '"x"'])
def test_parser_rejects_malformed_or_nonobject_json(alias: str, body: str) -> None:
    if body in ("[]", "null", "5", '"x"'):
        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_selection(alias, body)
    else:
        with pytest.raises(json.JSONDecodeError):
            parse_selection(alias, body)


@pytest.mark.parametrize(
    "body",
    [
        '{"config":{},"config":{}}',
        '{"config":{"eps_override":1,"eps_override":2}}',
        '{"config":{"unknown":{"same":1,"same":2}}}',
        '{"config":{"eps_override":1,"eps_\\u006fverride":2}}',
    ],
)
def test_parser_rejects_duplicate_keys_at_every_depth(body: str) -> None:
    with pytest.raises(ValueError, match="Duplicate configuration key"):
        parse_selection("graham-number", body)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
@pytest.mark.parametrize("alias", ["momentum", "graham-number", "graham-growth", "fcf-growth"])
def test_parser_rejects_nonfinite_json_anywhere(alias: str, token: str) -> None:
    with pytest.raises(ValueError, match="finite"):
        parse_selection(alias, '{"unknown":[{"nested":' + token + "}]}")  # rejects before field validation


@pytest.mark.parametrize("alias", ["momentum", "graham-number", "graham-growth", "fcf-growth"])
@pytest.mark.parametrize("field", ["ticker", "method_id", "analysis_id", "config_schema_version", "unknown"])
def test_parser_rejects_top_level_foreign_fields(alias: str, field: str) -> None:
    with pytest.raises(ValueError, match="configuration contains|Configuration body"):
        parse_selection(alias, json.dumps({field: 1}))


@pytest.mark.parametrize("alias", ["momentum", "graham-number", "graham-growth"])
@pytest.mark.parametrize(
    ("field", "value"),
    [("analysis_id", "graham"), ("method_id", "graham_number"), ("config_schema_version", 1)],
)
def test_parser_rejects_even_matching_identity_fields_in_config(alias: str, field: str, value: object) -> None:
    with pytest.raises(ValueError, match="identifiers and version"):
        parse_selection(alias, json.dumps({"config": {field: value}}))


@pytest.mark.parametrize("alias", ["momentum", "graham-number", "graham-growth"])
@pytest.mark.parametrize("value", [None, [], 1, "{}", False])
def test_parser_requires_config_object_when_present(alias: str, value: object) -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        parse_selection(alias, json.dumps({"config": value}))


@pytest.mark.parametrize(
    ("alias", "body"),
    [
        ("momentum", {"config": {"as_of": None}}),
        ("momentum", {"config": {"unknown": 1}}),
        ("momentum", {"config": {"short_window": None}}),
        ("momentum", {"config": {"rsi_period": None}}),
        ("graham-number", {"config": {"expected_growth": 5}}),
        ("graham-growth", {"config": {"expected_growth": 5, "aaa_yield_override": 4.5, "bvps_override": 2}}),
        ("graham-growth", {}),
        ("graham-growth", {"config": {}}),
        ("fcf-growth", {"policy": {"unknown": 1}}),
        ("fcf-growth", {"policy": {"method_id": "reported_fcf_eps_cagr"}}),
        ("fcf-growth", {"policy": None}),
        ("fcf-growth", {"policy": []}),
    ],
)
def test_parser_enforces_method_and_nested_field_allowlists(alias: str, body: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        parse_selection(alias, json.dumps(body))


def test_parser_materializes_omitted_defaults_and_preserves_explicit_fields() -> None:
    assert tuple(parse_selection(alias, "{}") for alias in ("momentum", "graham-number", "fcf-growth")) == (
        MomentumSelection.from_settings(),
        GrahamNumberSelection(),
        FCFGrowthSelection(),
    )
    momentum = parse_selection("momentum", '{"config":{"short_window":1,"rsi_period":1}}')
    assert isinstance(momentum, MomentumSelection)
    assert (momentum.short_window, momentum.long_window, momentum.rsi_period) == (1, 5, 1)
    number = parse_selection("graham-number", '{"config":{"security_provider_id":" MASSIVE ","bvps_override":0}}')
    assert isinstance(number, GrahamNumberSelection)
    assert number.to_graham_number_config().bvps_override == 0
    assert (number.eps_basis, number.quote_provider_id) == ("ttm", "massive")
    fcf = parse_selection(
        "fcf-growth",
        '{"policy":{"historical_horizon":"4","include_fcf_yield":false},"currency":" cad ","use_cache":false}',
    )
    assert isinstance(fcf, FCFGrowthSelection)
    assert fcf.currency == "CAD"
    assert fcf.use_cache is False
    assert fcf.to_fcf_policy() == FCFEarningsGrowthPolicy(
        historical_horizon=HistoricalHorizon.FOUR_YEARS, include_fcf_yield=False
    )


def test_explicit_config_round_trips_without_settings_or_external_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Parsing explicit request data must not read mutable/external state")

    # Imports have already completed; these guards cover the parsing/conversion operation.
    monkeypatch.setattr("src.config.ProjectSettings.get_momentum_analysis", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("pathlib.Path.open", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("sqlite3.connect", forbidden)
    monkeypatch.setattr("os.getenv", forbidden)
    examples = [
        ("momentum", {"config": {"short_window": 2, "long_window": 5, "rsi_period": 1}}),
        ("graham-number", {"config": {"eps_override": -1, "bvps_override": 0}}),
        ("graham-growth", {"config": {"expected_growth": -5, "aaa_yield_override": 0}}),
        ("fcf-growth", {"policy": {"forward_policy": "confirmation"}, "as_of": "2025-01-01T00:00:00Z"}),
    ]
    for alias, body in examples:
        selection = parse_selection(alias, json.dumps(body))
        values = selection.model_dump(mode="json", exclude={"analysis_id", "method_id", "config_schema_version"})
        serialized = json.dumps(values if alias == "fcf-growth" else {"config": values}, sort_keys=True)
        assert parse_selection(alias, serialized) == selection
        assert parse_selection(alias, serialized).model_dump_json() == selection.model_dump_json()
        if isinstance(selection, MomentumSelection):
            assert selection.to_momentum_config().rsi_period == 1
        elif isinstance(selection, GrahamNumberSelection):
            assert selection.to_graham_number_config().eps_override == -1
        elif isinstance(selection, GrahamGrowthSelection):
            assert selection.to_graham_growth_config().expected_growth == -5
        else:
            assert selection.to_fcf_policy().forward_policy is ForwardPolicy.CONFIRMATION


@pytest.mark.parametrize("version", [True, False, 1.0, "1", 0, 2])
def test_union_rejects_version_type_coercion(all_selections: tuple[AnalysisSelection, ...], version: object) -> None:
    for selection in all_selections:
        values = selection.model_dump()
        values["config_schema_version"] = version
        with pytest.raises(ValidationError):
            AnalysisRequest.model_validate({"ticker": "KO", "selection": values})
