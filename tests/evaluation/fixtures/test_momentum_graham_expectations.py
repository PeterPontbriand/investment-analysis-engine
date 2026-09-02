"""Fixture-focused checks for the reviewed Momentum and Graham expectation inputs."""

import math

import pandas as pd
import pytest

from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind
from src.data.instrument_profile import InstrumentKind
from src.evaluation.fixtures.graham import (
    AAA_YIELD_VALUE,
    BVPS_VALUE,
    EPS_FY2022,
    EPS_FY2023,
    EPS_FY2024,
    EPS_TTM,
    GOLDEN_BASELINE_AAA_YIELD,
    GOLDEN_EXPECTED_GROWTH,
    GOLDEN_GROWTH_BASE_PE,
    GOLDEN_GROWTH_MULTIPLIER,
    GOLDEN_HISTORICAL_AS_OF,
    GOLDEN_PRECEDENCE_BVPS_CACHE,
    GOLDEN_PRECEDENCE_EPS_OVERRIDE,
    PROVIDER_ID,
    QUOTE_VALUE,
    SECURITY_ID,
    SUBJECT_MISSING_QUOTE,
    FixtureFinancialFactsProvider,
)
from src.evaluation.fixtures.instrument_profiles import (
    GOLDEN_ETF_NAME,
    GOLDEN_ETF_TICKER,
    fixture_known_etf_profile,
)
from src.evaluation.fixtures.market_data import (
    MOMENTUM_BOUNDARY_CLOSES,
    MOMENTUM_LONG_WINDOW,
    MOMENTUM_RSI_PERIOD,
    MOMENTUM_SHORT_WINDOW,
    MOMENTUM_SUCCESS_CLOSES,
    momentum_boundary_frame,
    momentum_success_frame,
)


def test_momentum_success_fixture_has_exact_reviewed_inputs() -> None:
    frame = momentum_success_frame()

    assert tuple(float(value) for value in frame["Close"]) == MOMENTUM_SUCCESS_CLOSES
    assert len(frame) == 5
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert frame.index.tz is not None
    assert frame.index.is_monotonic_increasing
    assert MOMENTUM_SHORT_WINDOW == 2
    assert MOMENTUM_LONG_WINDOW == 3
    assert MOMENTUM_RSI_PERIOD == 3


def test_momentum_frames_are_fresh_and_do_not_share_mutable_state() -> None:
    first = momentum_success_frame()
    first.iloc[0, 0] = -1.0

    assert float(momentum_success_frame().iloc[0]["Close"]) == 100.0


def test_momentum_success_reference_arithmetic() -> None:
    closes = MOMENTUM_SUCCESS_CLOSES
    short_sma = sum(closes[-MOMENTUM_SHORT_WINDOW:]) / MOMENTUM_SHORT_WINDOW
    long_sma = sum(closes[-MOMENTUM_LONG_WINDOW:]) / MOMENTUM_LONG_WINDOW
    changes = tuple(current - previous for previous, current in zip(closes[:-1], closes[1:], strict=True))
    trailing_changes = changes[-MOMENTUM_RSI_PERIOD:]
    average_gain = sum(max(change, 0.0) for change in trailing_changes) / MOMENTUM_RSI_PERIOD
    average_loss = sum(max(-change, 0.0) for change in trailing_changes) / MOMENTUM_RSI_PERIOD
    rsi = 100.0 if average_loss == 0.0 and average_gain > 0.0 else math.nan

    assert closes[-1] == 104.0
    assert short_sma == 103.5
    assert long_sma == 103.0
    assert short_sma > long_sma
    assert rsi == 100.0


def test_momentum_boundary_fixture_is_one_observation_short_of_long_window() -> None:
    frame = momentum_boundary_frame()

    assert tuple(float(value) for value in frame["Close"]) == MOMENTUM_BOUNDARY_CLOSES
    assert len(frame) == MOMENTUM_LONG_WINDOW - 1
    assert sum(MOMENTUM_BOUNDARY_CLOSES) / MOMENTUM_SHORT_WINDOW == 100.5
    assert len(frame) <= MOMENTUM_RSI_PERIOD


def test_graham_three_year_reference_arithmetic() -> None:
    average_eps = (EPS_FY2022 + EPS_FY2023 + EPS_FY2024) / 3.0
    indicated_price = math.sqrt(22.5 * average_eps * BVPS_VALUE)
    margin = (indicated_price - QUOTE_VALUE) / indicated_price * 100.0

    assert average_eps == pytest.approx(3.2333333333333334, abs=1e-15)
    assert indicated_price == pytest.approx(36.68616905592624, abs=1e-12)
    assert margin == pytest.approx(-42.56053806073687, abs=1e-12)


def test_graham_ttm_reference_arithmetic() -> None:
    indicated_price = math.sqrt(22.5 * EPS_TTM * BVPS_VALUE)
    margin = (indicated_price - QUOTE_VALUE) / indicated_price * 100.0

    assert indicated_price == pytest.approx(44.69899327725402, abs=1e-12)
    assert margin == pytest.approx(-17.00487229231157, abs=1e-12)


def test_graham_growth_reference_arithmetic_and_method_discrimination() -> None:
    valuation_pe = GOLDEN_GROWTH_BASE_PE + GOLDEN_GROWTH_MULTIPLIER * GOLDEN_EXPECTED_GROWTH
    growth_value = EPS_TTM * valuation_pe * GOLDEN_BASELINE_AAA_YIELD / AAA_YIELD_VALUE
    margin = (growth_value - QUOTE_VALUE) / growth_value * 100.0
    ttm_graham_number = math.sqrt(22.5 * EPS_TTM * BVPS_VALUE)

    assert valuation_pe == 21.5
    assert growth_value == pytest.approx(109.41686746987952, abs=1e-12)
    assert margin == pytest.approx(52.20115398167724, abs=1e-12)
    assert growth_value != pytest.approx(ttm_graham_number, abs=1e-9)


def test_precedence_reference_inputs_produce_reviewed_value() -> None:
    indicated_price = math.sqrt(22.5 * GOLDEN_PRECEDENCE_EPS_OVERRIDE * GOLDEN_PRECEDENCE_BVPS_CACHE)
    margin = (indicated_price - QUOTE_VALUE) / indicated_price * 100.0

    assert indicated_price == pytest.approx(47.43416490252569, abs=1e-12)
    assert margin == pytest.approx(-10.258081084537493, abs=1e-12)


def test_historical_as_of_excludes_latest_annual_eps_publication() -> None:
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=SECURITY_ID,
        field_name=FinancialField.EPS,
        provider_id=PROVIDER_ID,
        basis="fiscal_year",
        observation_count=3,
    )
    facts = FixtureFinancialFactsProvider().fetch_facts(request)
    eligible = tuple(
        fact for fact in facts if fact.available_at is not None and fact.available_at <= GOLDEN_HISTORICAL_AS_OF
    )

    assert tuple(fact.value for fact in eligible) == (EPS_FY2022, EPS_FY2023)
    assert len(eligible) == 2


def test_missing_quote_subject_retains_required_facts_but_omits_quote() -> None:
    provider = FixtureFinancialFactsProvider()
    annual_eps = provider.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=SUBJECT_MISSING_QUOTE,
            field_name=FinancialField.EPS,
            provider_id=PROVIDER_ID,
            basis="fiscal_year",
            observation_count=3,
        )
    )
    bvps = provider.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=SUBJECT_MISSING_QUOTE,
            field_name=FinancialField.BVPS,
            provider_id=PROVIDER_ID,
        )
    )
    quote = provider.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=SUBJECT_MISSING_QUOTE,
            field_name=FinancialField.CURRENT_PRICE,
            provider_id=PROVIDER_ID,
        )
    )

    assert tuple(fact.value for fact in annual_eps) == (EPS_FY2022, EPS_FY2023, EPS_FY2024)
    assert all(fact.subject_id == SUBJECT_MISSING_QUOTE for fact in annual_eps)
    assert len(bvps) == 1
    assert bvps[0].value == BVPS_VALUE
    assert bvps[0].subject_id == SUBJECT_MISSING_QUOTE
    assert quote == ()


def test_known_etf_profile_is_affirmative_provider_evidence() -> None:
    profile = fixture_known_etf_profile()

    assert profile.ticker == GOLDEN_ETF_TICKER
    assert profile.identity is not None
    assert profile.identity.instrument_name == GOLDEN_ETF_NAME
    assert profile.kind_evidence is not None
    assert profile.kind_evidence.kind is InstrumentKind.ETF
    assert profile.kind_evidence.provider_id == "yfinance"
    assert profile.kind_evidence.provider_value == "ETF"
