"""Focused tests for typed, immutable workspace analysis selections."""

import json
from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from investment_analysis_engine.evaluation.strategy_fixtures import EVALUATION_STRATEGIES
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthPolicy
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection, FCFPolicySnapshot
from investment_analysis_engine.strategies.fcf_growth.vocabulary import (
    FCFClassificationBasis,
    ForwardPolicy,
    HistoricalHorizon,
)
from investment_analysis_engine.strategies.graham_growth.config import GrahamGrowthConfig
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.config import GrahamNumberConfig
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.analyzer import MomentumConfig
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.momentum.settings import MomentumSettings
from investment_analysis_engine.workspace.requests import AnalysisRequest
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from investment_analysis_engine.workspace.watchlists import StoredSelectionError, decode_selection, encode_selection

_SETTINGS = MomentumSettings(short_window=2, long_window=5, rsi_period=14, history_start_date=date(2026, 1, 1))


def _momentum(**overrides: Any) -> MomentumSelection:
    """Build a selection from the test settings, with any further field given explicitly."""
    return MomentumSelection(
        short_window=_SETTINGS.short_window,
        long_window=_SETTINGS.long_window,
        rsi_period=_SETTINGS.rsi_period,
        **overrides,
    )


def test_fixed_identifiers_and_schema_version() -> None:
    momentum = _momentum()
    assert momentum.analysis_id == "momentum"
    assert (momentum.method_id, momentum.config_schema_version) == ("sma_crossover", 2)

    graham = GrahamNumberSelection()
    assert graham.analysis_id == "graham_number"
    assert (graham.method_id, graham.config_schema_version) == ("graham_number", 2)


def test_momentum_selection_carries_the_given_values_into_its_config() -> None:
    selection = _momentum()
    assert (selection.short_window, selection.long_window, selection.rsi_period) == (2, 5, 14)

    config = selection.to_momentum_config()
    assert isinstance(config, MomentumConfig)
    assert (config.short_window, config.long_window, config.rsi_period) == (2, 5, 14)


def test_momentum_as_of_and_use_cache_default_and_reach_the_context() -> None:
    default = _momentum()
    assert (default.as_of, default.use_cache) == (None, True)
    executed_at = datetime(2026, 9, 1, tzinfo=UTC)
    context = default.to_analysis_context(executed_at)
    assert (context.as_of, context.use_cache, context.executed_at) == (None, True, executed_at)

    boundary = datetime(2025, 1, 1, tzinfo=UTC)
    explicit = _momentum(as_of=boundary, use_cache=False)
    context = explicit.to_analysis_context(executed_at)
    assert (context.as_of, context.use_cache) == (boundary, False)
    assert MomentumSelection.model_validate_json(explicit.model_dump_json()) == explicit


def test_momentum_rejects_naive_as_of_and_non_boolean_use_cache() -> None:
    with pytest.raises(ValidationError, match="timezone_aware"):
        _momentum(as_of=datetime(2025, 1, 1))
    with pytest.raises(ValidationError, match="bool"):
        _momentum(use_cache="no")


def test_momentum_rejects_the_previous_selection_version() -> None:
    with pytest.raises(ValidationError, match="config_schema_version"):
        MomentumSelection.model_validate({"short_window": 2, "long_window": 5, "config_schema_version": 1})


def test_momentum_snapshot_is_independent_of_caller_inputs() -> None:
    caller_values = {"short_window": 20, "long_window": 60, "rsi_period": 14}
    selection = MomentumSelection.model_validate(caller_values)
    caller_values.update(short_window=1, long_window=2)

    assert (selection.short_window, selection.long_window, selection.rsi_period) == (20, 60, 14)
    assert (selection.to_momentum_config().short_window, selection.to_momentum_config().long_window) == (20, 60)


def test_momentum_rejects_foreign_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        MomentumSelection(expected_growth=5.0)  # type: ignore[call-arg]


def test_momentum_rejects_invalid_windows() -> None:
    for value in (0, -1):
        with pytest.raises(ValidationError):
            MomentumSelection(short_window=value, long_window=5, rsi_period=14)
        with pytest.raises(ValidationError):
            MomentumSelection(short_window=2, long_window=5, rsi_period=value)

    with pytest.raises(ValidationError, match="smaller than long_window"):
        MomentumSelection(short_window=5, long_window=5, rsi_period=14)
    with pytest.raises(ValidationError, match="smaller than long_window"):
        MomentumSelection(short_window=10, long_window=2, rsi_period=14)


@pytest.mark.parametrize("field", ["short_window", "long_window", "rsi_period"])
def test_momentum_selection_is_frozen(field: str) -> None:
    selection = _momentum()
    with pytest.raises(ValidationError):
        setattr(selection, field, 1)


def test_graham_defaults_resolve_like_analyzer_config() -> None:
    selection = GrahamNumberSelection(security_provider_id="sec_edgar", bvps_override=20.0)
    config = selection.to_graham_number_config()

    assert isinstance(config, GrahamNumberConfig)
    assert selection.quote_provider_id == "yfinance"
    assert selection.use_cache is True


def test_graham_number_defaults() -> None:
    selection = GrahamNumberSelection()
    assert (selection.security_provider_id, selection.quote_provider_id) == ("sec_edgar", "yfinance")
    assert selection.use_cache is True


def test_graham_normalization_and_explicit_values() -> None:
    as_of = datetime(2025, 1, 1, tzinfo=UTC)
    selection = GrahamNumberSelection.model_validate(
        {
            "security_provider_id": " SEC_EDGAR ",
            "quote_provider_id": " YFINANCE ",
            "eps_override": 4.5,
            "bvps_override": 20.0,
            "quote_override": 100.0,
            "as_of": as_of,
            "use_cache": False,
        }
    )
    assert (selection.security_provider_id, selection.quote_provider_id) == ("sec_edgar", "yfinance")
    config = selection.to_graham_number_config()
    assert (config.eps_override, config.bvps_override, config.quote_override) == (4.5, 20.0, 100.0)
    assert selection.as_of == as_of
    assert selection.use_cache is False


def test_graham_snapshot_is_independent_of_caller_inputs() -> None:
    caller_values = {"eps_override": 4.5, "bvps_override": 25.0}
    selection = GrahamNumberSelection.model_validate(caller_values)
    caller_values.update(eps_override=9.9)

    assert selection.eps_override == 4.5
    assert selection.to_graham_number_config().eps_override == 4.5


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"security_provider_id": "massive"}, "Unsupported security provider"),
        ({"quote_provider_id": "massive"}, "Unsupported quote provider"),
        ({"eps_basis": "three_year_average"}, "extra_forbidden"),
        ({"eps_basis": "ttm"}, "extra_forbidden"),
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
    [("analysis_id", "wrong"), ("method_id", "wrong"), ("config_schema_version", 99)],
)
def test_identity_overrides_rejected(
    model: type[MomentumSelection] | type[GrahamNumberSelection], field: str, value: object
) -> None:
    values: dict[str, object] = (
        {"short_window": 2, "long_window": 5, "rsi_period": 14} if model is MomentumSelection else {}
    )
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


def test_converted_config_cannot_change_snapshot() -> None:
    selection = _momentum()
    converted = selection.to_momentum_config()
    converted.short_window = 1
    assert selection.short_window == 2
    assert selection.to_momentum_config().short_window == 2


def test_round_trip_and_conversion_do_not_read_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    momentum = _momentum()
    graham = GrahamNumberSelection(as_of=datetime(2025, 1, 1, tzinfo=UTC))

    def forbidden_settings(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Snapshot reconstruction must not read settings")

    monkeypatch.setattr(
        "investment_analysis_engine.config.strategy_settings.load_strategy_settings", forbidden_settings
    )
    assert MomentumSelection.model_validate_json(momentum.model_dump_json()) == momentum
    assert GrahamNumberSelection.model_validate_json(graham.model_dump_json()) == graham
    assert momentum.to_momentum_config().short_window == 2
    assert graham.to_analysis_context(executed_at=graham.as_of or datetime.now(UTC)).as_of == graham.as_of
    assert _momentum() == momentum


@pytest.mark.parametrize("missing", ["expected_growth", "aaa_yield_override"])
def test_growth_requires_each_explicit_assumption(missing: str) -> None:
    values = {"expected_growth": 5.0, "aaa_yield_override": 4.5}
    del values[missing]
    with pytest.raises(ValidationError) as error:
        GrahamGrowthSelection.model_validate(values)
    assert [item["loc"] for item in error.value.errors()] == [(missing,)]


@pytest.mark.parametrize("growth", [0.0, -5.0, 5.0])
def test_growth_conversion_preserves_assumptions(growth: float) -> None:
    selection = GrahamGrowthSelection(security_provider_id="sec_edgar", expected_growth=growth, aaa_yield_override=0.0)
    expected = GrahamGrowthConfig(security_provider_id="sec_edgar", expected_growth=growth, aaa_yield_override=0.0)
    assert selection.to_graham_growth_config() == expected
    assert (selection.eps_basis, selection.quote_provider_id) == ("three_year_average", "yfinance")


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
        {"security_provider_id": "massive"},
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
        {"provider_id": "yfinance"},
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
    return _stored_examples()


def test_all_request_variants_round_trip_without_settings(
    all_selections: tuple[AnalysisSelection, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_settings(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Request replay must not read settings")

    monkeypatch.setattr(
        "investment_analysis_engine.config.strategy_settings.load_strategy_settings", forbidden_settings
    )
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
        for field, invalid in [("analysis_id", "wrong"), ("method_id", "wrong"), ("config_schema_version", 99)]:
            payload = selection.model_dump()
            payload[field] = invalid
            with pytest.raises(ValidationError):
                AnalysisRequest.model_validate({"ticker": "KO", "selection": payload})


def _stored_examples() -> tuple[AnalysisSelection, ...]:
    """Return each declared strategy's own sample selection, so a new strategy needs no edit here."""
    return tuple(strategy.sample_selection for strategy in EVALUATION_STRATEGIES)


def test_stored_selection_round_trips_without_settings_or_external_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Decoding a stored selection must not read mutable/external state")

    # Imports have already completed; these guards cover the encode and decode operations.
    monkeypatch.setattr("investment_analysis_engine.config.strategy_settings.load_strategy_settings", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("pathlib.Path.open", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("sqlite3.connect", forbidden)
    monkeypatch.setattr("os.getenv", forbidden)
    for selection in _stored_examples():
        stored = encode_selection(selection)
        restored = decode_selection(selection.method_id, selection.config_schema_version, stored)
        assert restored == selection
        assert encode_selection(restored) == stored


@pytest.mark.parametrize("index", range(len(EVALUATION_STRATEGIES)))
def test_stored_selection_rejects_unknown_foreign_and_mistyped_fields(index: int) -> None:
    selection = _stored_examples()[index]
    stored = json.loads(encode_selection(selection))
    mutations: list[dict[str, object]] = [
        {**stored, "unknown": 1},
        {**stored, "ticker": "KO"},
        {**stored, "analysis_id": "wrong"},
        {**stored, "method_id": "wrong"},
    ]
    for key in stored:
        if key not in {"analysis_id", "method_id", "config_schema_version"}:
            mutations.append({**stored, key: {"wrong": "type"}})
    for mutated in mutations:
        with pytest.raises(StoredSelectionError):
            decode_selection(selection.method_id, selection.config_schema_version, json.dumps(mutated))


@pytest.mark.parametrize(
    "mutation",
    [
        {"policy": {"unknown": 1}},
        {"policy": {"method_id": "reported_fcf_eps_cagr"}},
        {"policy": None},
        {"policy": []},
    ],
)
def test_stored_fcf_selection_enforces_the_nested_policy_allowlist(mutation: dict[str, object]) -> None:
    selection = FCFGrowthSelection()
    stored = {**json.loads(encode_selection(selection)), **mutation}
    with pytest.raises(StoredSelectionError):
        decode_selection(selection.method_id, selection.config_schema_version, json.dumps(stored))


@pytest.mark.parametrize("version", [True, False, 1.0, "1", 2.0, "2", 0, 99])
def test_union_rejects_version_type_coercion(all_selections: tuple[AnalysisSelection, ...], version: object) -> None:
    for selection in all_selections:
        values = selection.model_dump()
        values["config_schema_version"] = version
        with pytest.raises(ValidationError):
            AnalysisRequest.model_validate({"ticker": "KO", "selection": values})
