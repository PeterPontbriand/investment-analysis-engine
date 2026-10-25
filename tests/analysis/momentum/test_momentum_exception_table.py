"""One test per row of Momentum's exception table: what is stored as a run and what still raises.

The rows are numbered as in the slice plan. A provider failure, a failed quality check and no observation at or
before the boundary return a run without metrics; a short history returns a run with an unknown trend; a caller
defect, a wiring defect and any other exception keep raising.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.constants import TrendStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.market_data import HistoricalMarketData, MarketDataContext
from investment_analysis_engine.data.quality import (
    HistoricalDataQualityError,
    QualityContext,
    QualityDecision,
    QualityOutcome,
    evaluate_historical_quality,
)
from investment_analysis_engine.strategies.momentum.analyzer import (
    MomentumAnalyzer,
    MomentumConfig,
    MomentumInputResolver,
    MomentumRun,
    compute_momentum_metrics,
)
from tests._momentum_runs import assert_no_series_resolved, assert_not_calculated

EXECUTED_AT = datetime(2026, 2, 1, tzinfo=UTC)
CONFIG = MomentumConfig(short_window=2, long_window=5, rsi_period=2)
SECRET = "yfinance 429 for https://example.invalid/?token=abc123"


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes}, index=pd.date_range("2026-01-01", periods=len(closes), tz=UTC))


def _data(closes: list[float]) -> HistoricalMarketData:
    return HistoricalMarketData(
        _frame(closes),
        MarketDataContext(
            provider_id="fixture",
            observation_interval="1d",
            currency="USD",
            observation_count=len(closes),
            data_as_of=pd.Timestamp("2026-01-01").date() + pd.Timedelta(days=len(closes) - 1),
        ),
    )


def _provider(data: HistoricalMarketData | None = None, *, error: BaseException | None = None) -> MagicMock:
    provider = MagicMock()
    provider.provider_id = "fixture"
    if error is not None:
        provider.fetch_historical_data.side_effect = error
    else:
        provider.fetch_historical_data.return_value = data
    return provider


def _run(provider: MagicMock, *, as_of: datetime | None = None, ticker: str = "ACME") -> MomentumRun:
    analyzer = MomentumAnalyzer(market_data_provider=provider, start_date="2026-01-01")
    return analyzer.run_analysis(ticker, CONFIG, AnalysisContext(as_of=as_of, executed_at=EXECUTED_AT, use_cache=True))


# Row 1 -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(ProviderFailureKind))
@pytest.mark.parametrize("as_of", [None, datetime(2026, 1, 20, tzinfo=UTC)], ids=["live", "as_of"])
def test_row_1_a_classified_provider_failure_is_stored_with_its_record(
    kind: ProviderFailureKind, as_of: datetime | None
) -> None:
    run = _run(_provider(error=DataFetchError(SECRET, kind=kind, provider_id="yfinance")), as_of=as_of)

    assert_not_calculated(run, CalculationStatus.PROVIDER_ERROR, code=ReasonCode.PROVIDER_ERROR)
    assert_no_series_resolved(run)
    assert run.provider_failure == ProviderFailureRecord(kind, "yfinance", "historical_close")
    assert run.reason == "Historical prices could not be retrieved from the market-data provider."
    assert "abc123" not in run.reason
    assert "abc123" not in repr(run.resolution_trace)
    assert [event.outcome.value for event in run.resolution_trace.events] == ["attempted", "error"]


def test_row_1_an_unclassified_provider_failure_is_stored_without_a_record() -> None:
    run = _run(_provider(error=DataFetchError(SECRET)))

    assert_not_calculated(run, CalculationStatus.PROVIDER_ERROR, code=ReasonCode.PROVIDER_ERROR)
    assert run.provider_failure is None
    assert "abc123" not in repr(run)


# Row 2 is the cached client's own check, exercised through the real cached client in test_momentum_as_of_fetch.py;
# here the same error type is raised by the provider call itself.


def test_row_2_a_quality_error_raised_inside_the_fetch_is_a_failed_quality_check() -> None:
    error = HistoricalDataQualityError(
        (
            QualityDecision(
                "historical.numeric",
                QualityOutcome.FAIL,
                "Close contains non-finite values.",
                QualityContext("ACME:h", EXECUTED_AT, None),
            ),
        ),
        _frame([1.0, float("nan")]),
    )

    run = _run(_provider(error=error))

    assert_not_calculated(run, CalculationStatus.INPUT_UNAVAILABLE, code=None, reason_contains="non-finite")
    assert_no_series_resolved(run)
    assert run.provider_failure is None


# Row 3 -------------------------------------------------------------------------------------------------------


def test_row_3_a_boundary_before_the_start_date_is_unavailable_without_a_fetch() -> None:
    provider = _provider(_data([1.0]))

    run = _run(provider, as_of=datetime(2025, 6, 1, tzinfo=UTC))

    assert_not_calculated(run, CalculationStatus.INPUT_UNAVAILABLE, code=ReasonCode.NOT_AVAILABLE_AS_OF)
    provider.fetch_historical_data.assert_not_called()


def test_row_3_an_empty_frame_after_truncation_is_unavailable() -> None:
    run = _run(_provider(_data([1.0, 2.0, 3.0])), as_of=datetime(2026, 1, 1, tzinfo=UTC) - pd.Timedelta(seconds=1))

    assert_not_calculated(run, CalculationStatus.INPUT_UNAVAILABLE, code=ReasonCode.NOT_AVAILABLE_AS_OF)
    assert_no_series_resolved(run)


# Row 4 -------------------------------------------------------------------------------------------------------


def test_row_4_provider_data_failing_the_quality_check_is_unavailable_with_a_text_reason() -> None:
    run = _run(_provider(_data([1.0, float("nan"), 3.0, 4.0, 5.0, 6.0])))

    assert_not_calculated(run, CalculationStatus.INPUT_UNAVAILABLE, code=None, reason_contains="finite")
    assert_no_series_resolved(run)


# Row 5 -------------------------------------------------------------------------------------------------------


def test_row_5_the_second_check_on_the_frame_handed_to_calculation_is_one_mapping() -> None:
    calls: list[int] = []

    def second_call_fails(data: HistoricalMarketData, *, context: QualityContext) -> tuple[QualityDecision, ...]:
        calls.append(1)
        if len(calls) == 1:
            return tuple(evaluate_historical_quality(data, context=context))
        return (QualityDecision("historical.any_rule", QualityOutcome.FAIL, "A rule failed.", context),)

    with patch(
        "investment_analysis_engine.strategies.momentum.analyzer.evaluate_historical_quality", second_call_fails
    ):
        run = _run(_provider(_data([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])))

    assert len(calls) == 2
    assert_not_calculated(run, CalculationStatus.INPUT_UNAVAILABLE, code=None, reason_contains="A rule failed.")
    assert len(run.price_inputs) == 6, "The series resolved; only the second check failed."
    assert run.market_data.observation_count == 6
    assert run.resolution_trace.events[-1].outcome.value == "rejected"


# Row 6 -------------------------------------------------------------------------------------------------------


def test_row_6_a_series_exactly_the_long_window_is_ok() -> None:
    run = _run(_provider(_data([1.0, 2.0, 3.0, 4.0, 5.0])))

    assert run.execution_status is CalculationStatus.OK
    assert run.metrics is not None
    assert run.metrics.status is TrendStatus.BULLISH
    assert (run.reason, run.reason_code) == (None, None)


def test_row_6_one_observation_fewer_is_unavailable_with_the_trend_unknown_and_rsi_kept() -> None:
    run = _run(_provider(_data([1.0, 2.0, 3.0, 4.0])))

    assert run.execution_status is CalculationStatus.INPUT_UNAVAILABLE
    assert run.reason_code is ReasonCode.INSUFFICIENT_HISTORY
    assert run.reason == "The long moving average requires 5 observations; 4 were available."
    assert run.metrics is not None
    assert run.metrics.status is TrendStatus.UNKNOWN
    assert run.metrics.rsi_14.value == 100.0
    assert len(run.price_inputs) == 4


def test_row_6_rsi_is_absent_when_the_series_is_not_longer_than_the_rsi_period() -> None:
    run = _run(_provider(_data([1.0, 2.0])))

    assert run.execution_status is CalculationStatus.INPUT_UNAVAILABLE
    assert run.metrics is not None
    assert run.metrics.rsi_14.value is None
    assert run.metrics.rsi_14.reason_code is ReasonCode.INSUFFICIENT_HISTORY


# Rows 7 to 11 keep raising -----------------------------------------------------------------------------------


def test_row_7_a_naive_as_of_raises() -> None:
    resolver = MomentumInputResolver(_provider(_data([1.0])), clock=lambda: EXECUTED_AT)
    with pytest.raises(ValueError, match="must be timezone-aware"):
        resolver.resolve(
            ticker="ACME",
            start_date="2026-01-01",
            effective_as_of=EXECUTED_AT,
            use_cache=True,
            as_of=datetime(2026, 1, 10),
        )


def test_row_8_a_missing_provider_identity_raises() -> None:
    provider = _provider(
        HistoricalMarketData(_frame([1.0, 2.0, 3.0, 4.0, 5.0]), MarketDataContext(observation_interval="1d"))
    )
    provider.provider_id = None
    with pytest.raises(ValueError, match="provider identity is required"):
        _run(provider)


@pytest.mark.parametrize("ticker", ["", "   "])
def test_row_9_a_blank_ticker_raises(ticker: str) -> None:
    with pytest.raises(ValueError, match="ticker"):
        _run(_provider(_data([1.0])), ticker=ticker)


def test_row_9_an_invalid_config_raises() -> None:
    with pytest.raises(ValueError, match="smaller than Long window"):
        MomentumConfig(short_window=5, long_window=5, rsi_period=2)


def test_row_10_the_pure_calculator_still_raises_for_an_empty_frame_and_a_non_finite_close() -> None:
    timestamp = datetime(2026, 1, 20, tzinfo=UTC)
    with pytest.raises(ValueError, match="Insufficient historical data points"):
        compute_momentum_metrics(pd.DataFrame({"Close": []}), CONFIG, "ACME", timestamp)
    with pytest.raises(ValueError, match="latest close must be finite"):
        compute_momentum_metrics(pd.DataFrame({"Close": [1.0, float("nan")]}), CONFIG, "ACME", timestamp)


@pytest.mark.parametrize(
    "closes",
    [[], [1.0, 2.0, 3.0, 4.0, float("nan")], [1.0, 2.0, 3.0, 4.0, float("inf")]],
    ids=["empty", "nan-latest", "inf-latest"],
)
def test_row_10_is_unreachable_through_the_analyzer_because_the_quality_check_comes_first(
    closes: list[float],
) -> None:
    data = HistoricalMarketData(
        _frame(closes), MarketDataContext(provider_id="fixture", observation_interval="1d", currency="USD")
    )

    run = _run(_provider(data))

    assert_not_calculated(run, CalculationStatus.INPUT_UNAVAILABLE, code=None)


@pytest.mark.parametrize("error", [RuntimeError("defect"), KeyError("Close"), TypeError("bad")])
def test_row_11_any_other_exception_raises_unchanged(error: Exception) -> None:
    with pytest.raises(type(error)):
        _run(_provider(error=error))


def test_row_11_an_unrelated_value_error_is_not_swallowed() -> None:
    class _UnrelatedValueError(ValueError):
        pass

    with pytest.raises(_UnrelatedValueError):
        _run(_provider(error=_UnrelatedValueError("unrelated value error")))
