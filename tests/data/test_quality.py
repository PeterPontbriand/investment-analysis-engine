"""Deterministic quality decisions without provider calls or cache mutation."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.data.market_data import HistoricalMarketData, MarketDataContext
from src.data.quality import (
    FreshnessPolicy,
    HistoricalQualityPolicy,
    QualityContext,
    QualityDecision,
    QualityOutcome,
    evaluate_freshness,
    evaluate_historical_quality,
)

NOW = datetime(2026, 9, 7, tzinfo=UTC)
CONTEXT = QualityContext(input_id="ABC:daily", evaluated_at=NOW, retrieved_at=NOW)


def history() -> HistoricalMarketData:
    return HistoricalMarketData(
        pd.DataFrame({"Close": [100.0, 101.0]}, index=pd.to_datetime(["2026-09-03", "2026-09-04"])),
        MarketDataContext(
            currency="CAD",
            observation_interval="1d",
            price_adjustment="adjusted",
            observation_count=2,
            data_as_of=date(2026, 9, 4),
        ),
    )


def outcomes(decisions: tuple[QualityDecision, ...]) -> dict[str, QualityOutcome]:
    assert all(item.reason and item.context.input_id for item in decisions)
    return {item.rule_id: item.outcome for item in decisions}


def test_explicit_sessions_and_metadata_pass_without_mutation() -> None:
    data = history()
    original = data.frame.copy(deep=True)
    policy = HistoricalQualityPolicy(
        expected_currency=" cad ",
        expected_adjustment=" ADJUSTED ",
        expected_sessions=(date(2026, 9, 3), date(2026, 9, 4)),
    )
    decisions = evaluate_historical_quality(data, context=CONTEXT, policy=policy)
    assert set(outcomes(decisions).values()) == {QualityOutcome.PASS}
    assert all(item.context is CONTEXT for item in decisions)
    assert_frame_equal(data.frame, original)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), "bad", None, 1 + 2j, True])
def test_invalid_numeric_observations_are_rejected(value: object) -> None:
    data = replace(history(), frame=pd.DataFrame({"Close": [value]}, index=pd.to_datetime(["2026-09-04"])))
    assert outcomes(evaluate_historical_quality(data, context=CONTEXT))["historical.numeric"] is QualityOutcome.FAIL


@pytest.mark.parametrize(
    "frame", [pd.DataFrame(), pd.DataFrame({"Open": [1.0]}), pd.DataFrame([[1.0, 2.0]], columns=["Close", "Close"])]
)
def test_empty_missing_close_and_duplicate_columns_fail(frame: pd.DataFrame) -> None:
    result = evaluate_historical_quality(replace(history(), frame=frame), context=CONTEXT)
    assert outcomes(result)["historical.numeric"] is QualityOutcome.FAIL


@pytest.mark.parametrize("column", ["Open", "High", "Low", "Adj Close", "Volume"])
def test_all_present_price_and_volume_columns_are_checked(column: str) -> None:
    data = history()
    data.frame[column] = [1.0, np.nan]
    assert outcomes(evaluate_historical_quality(data, context=CONTEXT))["historical.numeric"] is QualityOutcome.FAIL


@pytest.mark.parametrize(
    "index",
    [
        pd.to_datetime(["2026-09-04", "2026-09-03"]),
        pd.to_datetime(["2026-09-03", "2026-09-03"]),
        pd.DatetimeIndex(["2026-09-03", None]),
    ],
)
def test_invalid_date_order_and_missing_dates_fail(index: pd.DatetimeIndex) -> None:
    data = history()
    data.frame.index = index
    assert outcomes(evaluate_historical_quality(data, context=CONTEXT))["historical.index"] is QualityOutcome.FAIL


def test_non_date_index_is_unverified_without_coercion() -> None:
    data = history()
    data.frame.index = pd.Index(["first", "second"])
    result = outcomes(evaluate_historical_quality(data, context=CONTEXT))
    assert result["historical.index"] is QualityOutcome.INSUFFICIENT_EVIDENCE
    assert result["historical.context"] is QualityOutcome.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    "metadata", [MarketDataContext(observation_count=3), MarketDataContext(data_as_of=date(2026, 9, 3))]
)
def test_contradictory_retained_context_fails(metadata: MarketDataContext) -> None:
    result = evaluate_historical_quality(replace(history(), context=metadata), context=CONTEXT)
    assert outcomes(result)["historical.context"] is QualityOutcome.FAIL


def test_unknown_evidence_is_never_a_verified_pass() -> None:
    result = outcomes(evaluate_historical_quality(replace(history(), context=MarketDataContext()), context=CONTEXT))
    for rule in ("historical.context", "historical.currency", "historical.adjustment", "historical.sessions"):
        assert result[rule] is QualityOutcome.INSUFFICIENT_EVIDENCE


def test_known_currency_and_adjustment_conflicts_fail() -> None:
    result = outcomes(
        evaluate_historical_quality(
            history(),
            context=CONTEXT,
            policy=HistoricalQualityPolicy(expected_currency="USD", expected_adjustment="unadjusted"),
        )
    )
    assert result["historical.currency"] is QualityOutcome.FAIL
    assert result["historical.adjustment"] is QualityOutcome.FAIL


def test_missing_expected_session_fails_without_weekday_inference() -> None:
    policy = HistoricalQualityPolicy(expected_sessions=(date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 7)))
    result = outcomes(evaluate_historical_quality(history(), context=CONTEXT, policy=policy))
    assert result["historical.sessions"] is QualityOutcome.FAIL
    # An omitted holiday is not synthesized as a required session.
    policy = replace(policy, expected_sessions=(date(2026, 9, 3), date(2026, 9, 4)))
    assert (
        outcomes(evaluate_historical_quality(history(), context=CONTEXT, policy=policy))["historical.sessions"]
        is QualityOutcome.PASS
    )


def test_intraday_schedule_cannot_claim_daily_gap_coverage() -> None:
    data = replace(history(), context=replace(history().context, observation_interval="1h"))
    result = evaluate_historical_quality(
        data, context=CONTEXT, policy=HistoricalQualityPolicy(expected_sessions=(date(2026, 9, 3),))
    )
    assert outcomes(result)["historical.sessions"] is QualityOutcome.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (9, QualityOutcome.PASS),
        (10, QualityOutcome.PASS),
        (11, QualityOutcome.FAIL),
        (-1, QualityOutcome.INSUFFICIENT_EVIDENCE),
    ],
)
def test_cache_age_boundary_and_clock_drift(age: int, expected: QualityOutcome) -> None:
    result = evaluate_freshness(
        context=CONTEXT, policy=FreshnessPolicy(cache_ttl=timedelta(seconds=10)), cached_at=NOW - timedelta(seconds=age)
    )
    assert outcomes(result)["freshness.cache_age"] is expected


def test_zero_ttl_and_disabled_limits_preserve_distinct_meanings() -> None:
    assert (
        outcomes(evaluate_freshness(context=CONTEXT, policy=FreshnessPolicy(cache_ttl=timedelta(0)), cached_at=NOW))[
            "freshness.cache_age"
        ]
        is QualityOutcome.PASS
    )
    assert (
        outcomes(evaluate_freshness(context=CONTEXT, policy=FreshnessPolicy(), cached_at=NOW))["freshness.cache_age"]
        is QualityOutcome.INSUFFICIENT_EVIDENCE
    )


@pytest.mark.parametrize(
    ("age", "expected"), [(10, QualityOutcome.PASS), (11, QualityOutcome.FAIL), (-1, QualityOutcome.FAIL)]
)
def test_observation_age_uses_analysis_time(age: int, expected: QualityOutcome) -> None:
    as_of = NOW - timedelta(days=100)
    context = replace(CONTEXT, analysis_as_of=as_of)
    result = evaluate_freshness(
        context=context,
        policy=FreshnessPolicy(observation_max_age=timedelta(days=10)),
        observed_at=as_of - timedelta(days=age),
        available_at=as_of,
    )
    assert outcomes(result)["freshness.observation_age"] is expected
    assert outcomes(result)["freshness.availability"] is QualityOutcome.PASS


def test_old_observation_without_age_policy_is_not_declared_stale_or_fresh() -> None:
    result = evaluate_freshness(context=CONTEXT, policy=FreshnessPolicy(), observed_at=NOW - timedelta(days=500))
    assert outcomes(result)["freshness.observation_age"] is QualityOutcome.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    ("historical", "available", "expected"),
    [
        (False, None, QualityOutcome.INSUFFICIENT_EVIDENCE),
        (True, None, QualityOutcome.FAIL),
        (False, NOW, QualityOutcome.PASS),
        (True, NOW, QualityOutcome.PASS),
        (False, NOW + timedelta(seconds=1), QualityOutcome.FAIL),
        (True, NOW + timedelta(seconds=1), QualityOutcome.FAIL),
    ],
)
def test_availability_boundary(historical: bool, available: datetime | None, expected: QualityOutcome) -> None:
    context = replace(CONTEXT, analysis_as_of=NOW if historical else None)
    result = evaluate_freshness(context=context, policy=FreshnessPolicy(), available_at=available)
    assert outcomes(result)["freshness.availability"] is expected


@pytest.mark.parametrize("field", ["cached_at", "observed_at", "available_at"])
def test_naive_evidence_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_freshness(context=CONTEXT, policy=FreshnessPolicy(), **{field: datetime(2026, 9, 7)})


@pytest.mark.parametrize("field", ["evaluated_at", "analysis_as_of", "retrieved_at"])
def test_naive_context_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        QualityContext(
            input_id=CONTEXT.input_id,
            evaluated_at=datetime(2026, 9, 7) if field == "evaluated_at" else NOW,
            analysis_as_of=datetime(2026, 9, 7) if field == "analysis_as_of" else None,
            retrieved_at=datetime(2026, 9, 7) if field == "retrieved_at" else None,
        )


def test_invalid_configuration_is_explicit() -> None:
    with pytest.raises(ValueError, match="input_id"):
        replace(CONTEXT, input_id=" ")
    with pytest.raises(ValueError, match="non-negative"):
        FreshnessPolicy(cache_ttl=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="non-negative"):
        FreshnessPolicy(observation_max_age=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="non-empty"):
        HistoricalQualityPolicy(expected_currency=" ")
    with pytest.raises(ValueError, match="non-empty"):
        HistoricalQualityPolicy(expected_adjustment=" ")
    with pytest.raises(ValueError, match="sessions"):
        HistoricalQualityPolicy(expected_sessions=())
    with pytest.raises(ValueError, match="sessions"):
        HistoricalQualityPolicy(expected_sessions=(date(2026, 9, 4), date(2026, 9, 3)))


@pytest.mark.parametrize("value", [True, np.bool_(True), 1 + 2j, np.complex64(1 + 2j)])
def test_mixed_object_values_do_not_hide_boolean_or_complex_data(value: object) -> None:
    data = history()
    data.frame["Close"] = pd.Series([1.0, value], index=data.frame.index, dtype=object)
    assert outcomes(evaluate_historical_quality(data, context=CONTEXT))["historical.numeric"] is QualityOutcome.FAIL


def test_numeric_strings_and_nullable_numeric_values_preserve_existing_conversion() -> None:
    data = history()
    data.frame["Close"] = pd.Series(["100.0", "101.0"], index=data.frame.index, dtype=object)
    data.frame["Volume"] = pd.Series([0, 100], index=data.frame.index, dtype="Int64")
    assert outcomes(evaluate_historical_quality(data, context=CONTEXT))["historical.numeric"] is QualityOutcome.PASS
    data.frame.loc[data.frame.index[0], "Volume"] = pd.NA
    assert outcomes(evaluate_historical_quality(data, context=CONTEXT))["historical.numeric"] is QualityOutcome.FAIL


def test_invalid_index_prevents_claiming_session_coverage() -> None:
    data = history()
    data.frame.index = pd.to_datetime(["2026-09-04", "2026-09-03"])
    result = evaluate_historical_quality(
        data, context=CONTEXT, policy=HistoricalQualityPolicy(expected_sessions=(date(2026, 9, 3),))
    )
    assert outcomes(result)["historical.sessions"] is QualityOutcome.INSUFFICIENT_EVIDENCE


def test_duplicate_daily_session_bars_fail() -> None:
    data = history()
    data.frame.index = pd.to_datetime(["2026-09-03 10:00", "2026-09-03 11:00"])
    result = evaluate_historical_quality(
        data, context=CONTEXT, policy=HistoricalQualityPolicy(expected_sessions=(date(2026, 9, 3),))
    )
    assert outcomes(result)["historical.sessions"] is QualityOutcome.FAIL


def test_exchange_local_dates_are_preserved_for_session_matching() -> None:
    data = history()
    data.frame.index = pd.to_datetime(["2026-09-03 23:00", "2026-09-04 23:00"]).tz_localize("America/Toronto")
    result = evaluate_historical_quality(
        data,
        context=CONTEXT,
        policy=HistoricalQualityPolicy(expected_sessions=(date(2026, 9, 3), date(2026, 9, 4))),
    )
    assert outcomes(result)["historical.sessions"] is QualityOutcome.PASS


def test_decisions_retain_exact_temporal_evidence() -> None:
    cached = NOW - timedelta(hours=1)
    observed = NOW - timedelta(days=10)
    available = NOW - timedelta(days=9)
    result = evaluate_freshness(
        context=CONTEXT, policy=FreshnessPolicy(), cached_at=cached, observed_at=observed, available_at=available
    )
    assert tuple(item.evidence_at for item in result) == (cached, observed, available)
    assert all(item.context is CONTEXT for item in result)


@pytest.mark.parametrize(("rule", "reason"), [("", "reason"), ("rule", " ")])
def test_decision_requires_rule_and_reason(rule: str, reason: str) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        QualityDecision(rule, QualityOutcome.PASS, reason, CONTEXT)


def test_naive_decision_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        QualityDecision("rule", QualityOutcome.PASS, "reason", CONTEXT, datetime(2026, 9, 7))


def test_duplicate_expected_dates_are_rejected() -> None:
    with pytest.raises(ValueError, match="sessions"):
        HistoricalQualityPolicy(expected_sessions=(date(2026, 9, 3), date(2026, 9, 3)))
