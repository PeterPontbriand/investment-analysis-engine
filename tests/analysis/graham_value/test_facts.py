"""Tests for src.data.financial.facts provider-neutral contracts.

Uses tiny in-test fakes only; no reusable fixture datasets.  All datetimes are
fixed timezone-aware values — no ``datetime.now()``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import inf, nan
from typing import Any

import pytest

from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialFactsProvider,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from src.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    FinancialSubjectKind,
    PeriodKind,
)

AW = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)  # aware
NAIVE = datetime(2025, 6, 1, 12, 0)  # naive
AS_OF = datetime(2025, 12, 31, tzinfo=UTC)
PERIOD_START = datetime(2024, 7, 1, tzinfo=UTC)
PERIOD_END = datetime(2025, 6, 30, tzinfo=UTC)


# ===========================================================================
# Enum members
# ===========================================================================


def test_valuation_field_members() -> None:
    assert FinancialField.CURRENT_PRICE.value == "current_price"
    assert FinancialField.EPS.value == "eps"
    assert FinancialField.BVPS.value == "bvps"
    assert FinancialField.CURRENT_AAA_YIELD.value == "current_aaa_yield"
    assert FinancialField.STOCKHOLDERS_EQUITY.value == "stockholders_equity"
    assert FinancialField.COMMON_SHARES_OUTSTANDING.value == "common_shares_outstanding"
    assert FinancialField.PREFERRED_SHARES_OUTSTANDING.value == "preferred_shares_outstanding"
    assert FinancialField.OPERATING_CASH_FLOW.value == "operating_cash_flow"
    assert FinancialField.CAPITAL_EXPENDITURES.value == "capital_expenditures"
    assert FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES.value == "weighted_average_diluted_shares"
    assert len(list(FinancialField)) == 10


def test_valuation_unit_members() -> None:
    assert FinancialUnit.CURRENCY_PER_SHARE.value == "currency_per_share"
    assert FinancialUnit.PERCENTAGE_POINTS.value == "percentage_points"
    assert FinancialUnit.CURRENCY.value == "currency"
    assert FinancialUnit.SHARES.value == "shares"
    assert len(list(FinancialUnit)) == 4


# ===========================================================================
# FinancialFactRequest — valid construction
# ===========================================================================


def test_valid_security_current_price_request() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.CURRENT_PRICE,
        provider_id="yfinance",
    )
    assert req.subject_kind is FinancialSubjectKind.SECURITY
    assert req.subject_id == "AAPL"
    assert req.field_name is FinancialField.CURRENT_PRICE
    assert req.provider_id == "yfinance"
    assert req.basis is None
    assert req.as_of is None
    assert req.observation_count == 1


def test_valid_security_eps_request() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.EPS,
        provider_id="yfinance",
        basis="ttm",
    )
    assert req.field_name is FinancialField.EPS
    assert req.basis == "ttm"


def test_valid_security_bvps_request() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="MSFT",
        field_name=FinancialField.BVPS,
        provider_id="yfinance",
    )
    assert req.field_name is FinancialField.BVPS


def test_valid_macro_aaa_yield_request() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.MACRO,
        subject_id="AAA",
        field_name=FinancialField.CURRENT_AAA_YIELD,
        provider_id="fred",
        as_of=AS_OF,
    )
    assert req.subject_kind is FinancialSubjectKind.MACRO
    assert req.field_name is FinancialField.CURRENT_AAA_YIELD
    assert req.as_of == AS_OF


# ===========================================================================
# FinancialFactRequest — normalization
# ===========================================================================


def test_security_symbol_normalization() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="  aapl  ",
        field_name=FinancialField.EPS,
        provider_id="yfinance",
    )
    assert req.subject_id == "AAPL"


def test_macro_id_case_preserved() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.MACRO,
        subject_id="  aaa  ",
        field_name=FinancialField.CURRENT_AAA_YIELD,
        provider_id="fred",
    )
    assert req.subject_id == "aaa"


def test_macro_id_uppercase_preserved() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.MACRO,
        subject_id="AAA",
        field_name=FinancialField.CURRENT_AAA_YIELD,
        provider_id="fred",
    )
    assert req.subject_id == "AAA"


def test_provider_id_canonicalization() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.EPS,
        provider_id="  YFinance  ",
    )
    assert req.provider_id == "yfinance"


# ===========================================================================
# FinancialFactRequest — rejection
# ===========================================================================


def test_request_empty_subject_id_rejected() -> None:
    with pytest.raises(ValueError, match="subject_id"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="   ",
            field_name=FinancialField.EPS,
            provider_id="yfinance",
        )


def test_request_empty_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.EPS,
            provider_id="   ",
        )


def test_request_empty_basis_rejected() -> None:
    with pytest.raises(ValueError, match="basis"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.EPS,
            provider_id="yfinance",
            basis="   ",
        )


def test_request_naive_as_of_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.EPS,
            provider_id="yfinance",
            as_of=NAIVE,
        )


def test_request_zero_observation_count_rejected() -> None:
    with pytest.raises(ValueError, match="observation_count"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.EPS,
            provider_id="yfinance",
            observation_count=0,
        )


def test_request_negative_observation_count_rejected() -> None:
    with pytest.raises(ValueError, match="observation_count"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.EPS,
            provider_id="yfinance",
            observation_count=-3,
        )


@pytest.mark.parametrize(
    "field_name",
    [FinancialField.EPS, FinancialField.OPERATING_CASH_FLOW, FinancialField.CAPITAL_EXPENDITURES],
)
def test_annual_fields_allow_multiple_observations(field_name: FinancialField) -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=field_name,
        provider_id="yfinance",
        basis="fiscal_year",
        observation_count=3,
    )
    assert req.observation_count == 3


@pytest.mark.parametrize(
    "field_name",
    [FinancialField.EPS, FinancialField.OPERATING_CASH_FLOW, FinancialField.CAPITAL_EXPENDITURES],
)
def test_multiple_observations_require_fiscal_year_basis(field_name: FinancialField) -> None:
    with pytest.raises(ValueError, match="basis='fiscal_year'"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=field_name,
            provider_id="fixture",
            basis="ttm",
            observation_count=3,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        FinancialField.CURRENT_PRICE,
        FinancialField.BVPS,
        FinancialField.CURRENT_AAA_YIELD,
        FinancialField.STOCKHOLDERS_EQUITY,
        FinancialField.COMMON_SHARES_OUTSTANDING,
        FinancialField.PREFERRED_SHARES_OUTSTANDING,
    ],
)
def test_multiple_observations_rejected_for_non_eps(field_name: FinancialField) -> None:
    subject_kind = (
        FinancialSubjectKind.MACRO if field_name is FinancialField.CURRENT_AAA_YIELD else FinancialSubjectKind.SECURITY
    )
    with pytest.raises(ValueError, match="observation_count"):
        FinancialFactRequest(
            subject_kind=subject_kind,
            subject_id="AAPL",
            field_name=field_name,
            provider_id="yfinance",
            observation_count=3,
        )


def test_aaa_yield_requires_macro() -> None:
    with pytest.raises(ValueError, match="MACRO"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.CURRENT_AAA_YIELD,
            provider_id="yfinance",
        )


def test_security_field_requires_security() -> None:
    with pytest.raises(ValueError, match="SECURITY"):
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.MACRO,
            subject_id="AAA",
            field_name=FinancialField.EPS,
            provider_id="fred",
        )


def test_request_frozen() -> None:
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.EPS,
        provider_id="yfinance",
    )
    with pytest.raises(AttributeError):
        req.provider_id = "other"  # type: ignore[misc]


# ===========================================================================
# ProviderFact — valid construction
# ===========================================================================


def test_valid_current_price_fact() -> None:
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.CURRENT_PRICE,
        value=210.5,
        units=FinancialUnit.CURRENCY_PER_SHARE,
        provider_id="yfinance",
        provider_field="regularMarketPrice",
        retrieved_at=AW,
        currency="USD",
    )
    assert fact.value == 210.5
    assert fact.currency == "USD"


def test_valid_eps_fact() -> None:
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.EPS,
        value=6.1,
        units=FinancialUnit.CURRENCY_PER_SHARE,
        provider_id="yfinance",
        provider_field="trailingEps",
        retrieved_at=AW,
        basis="ttm",
        currency="USD",
    )
    assert fact.field_name is FinancialField.EPS
    assert fact.basis == "ttm"


def test_valid_bvps_fact() -> None:
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="MSFT",
        field_name=FinancialField.BVPS,
        value=42.3,
        units=FinancialUnit.CURRENCY_PER_SHARE,
        provider_id="yfinance",
        provider_field="bookValue",
        retrieved_at=AW,
        currency="USD",
    )
    assert fact.value == 42.3


def test_valid_aaa_yield_fact() -> None:
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.MACRO,
        subject_id="AAA",
        field_name=FinancialField.CURRENT_AAA_YIELD,
        value=4.4,
        units=FinancialUnit.PERCENTAGE_POINTS,
        provider_id="fred",
        provider_field="FRED_AAA",
        retrieved_at=AW,
    )
    assert fact.value == 4.4
    assert fact.currency is None


def test_valid_stockholders_equity_fact() -> None:
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.STOCKHOLDERS_EQUITY,
        value=75_000_000_000.0,
        units=FinancialUnit.CURRENCY,
        provider_id="sec_edgar",
        provider_field="us-gaap:StockholdersEquity",
        retrieved_at=AW,
        basis="fiscal_year_end",
        currency="USD",
        observation_period_end=PERIOD_END,
    )
    assert fact.units is FinancialUnit.CURRENCY
    assert fact.currency == "USD"


def test_valid_common_shares_outstanding_fact() -> None:
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.COMMON_SHARES_OUTSTANDING,
        value=15_000_000_000.0,
        units=FinancialUnit.SHARES,
        provider_id="sec_edgar",
        provider_field="us-gaap:CommonStockSharesOutstanding",
        retrieved_at=AW,
        basis="fiscal_year_end",
        observation_period_end=PERIOD_END,
    )
    assert fact.units is FinancialUnit.SHARES
    assert fact.currency is None


def test_zero_preferred_shares_outstanding_is_valid_guard_fact() -> None:
    fact = ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.PREFERRED_SHARES_OUTSTANDING,
        value=0.0,
        units=FinancialUnit.SHARES,
        provider_id="sec_edgar",
        provider_field="us-gaap:PreferredStockSharesOutstanding",
        retrieved_at=AW,
        basis="fiscal_year_end",
        observation_period_end=PERIOD_END,
    )
    assert fact.value == 0.0


# ===========================================================================
# ProviderFact — finiteness
# ===========================================================================


def _base_fact_kwargs(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "subject_kind": FinancialSubjectKind.SECURITY,
        "subject_id": "AAPL",
        "field_name": FinancialField.EPS,
        "value": 5.0,
        "units": FinancialUnit.CURRENCY_PER_SHARE,
        "provider_id": "yfinance",
        "provider_field": "trailingEps",
        "retrieved_at": AW,
        "currency": "USD",
    }
    defaults.update(overrides)
    return defaults


def test_nan_value_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        ProviderFact(**_base_fact_kwargs(value=nan))


def test_pos_inf_value_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        ProviderFact(**_base_fact_kwargs(value=inf))


def test_neg_inf_value_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        ProviderFact(**_base_fact_kwargs(value=-inf))


# ===========================================================================
# ProviderFact — positivity rules
# ===========================================================================


def test_zero_current_price_rejected() -> None:
    with pytest.raises(ValueError, match="current_price"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.CURRENT_PRICE,
            value=0.0,
            units=FinancialUnit.CURRENCY_PER_SHARE,
            provider_id="yfinance",
            provider_field="regularMarketPrice",
            retrieved_at=AW,
            currency="USD",
        )


def test_negative_current_price_rejected() -> None:
    with pytest.raises(ValueError, match="current_price"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.CURRENT_PRICE,
            value=-1.0,
            units=FinancialUnit.CURRENCY_PER_SHARE,
            provider_id="yfinance",
            provider_field="regularMarketPrice",
            retrieved_at=AW,
            currency="USD",
        )


def test_zero_aaa_yield_rejected() -> None:
    with pytest.raises(ValueError, match="current_aaa_yield"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.MACRO,
            subject_id="AAA",
            field_name=FinancialField.CURRENT_AAA_YIELD,
            value=0.0,
            units=FinancialUnit.PERCENTAGE_POINTS,
            provider_id="fred",
            provider_field="FRED_AAA",
            retrieved_at=AW,
        )


def test_negative_aaa_yield_rejected() -> None:
    with pytest.raises(ValueError, match="current_aaa_yield"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.MACRO,
            subject_id="AAA",
            field_name=FinancialField.CURRENT_AAA_YIELD,
            value=-2.0,
            units=FinancialUnit.PERCENTAGE_POINTS,
            provider_id="fred",
            provider_field="FRED_AAA",
            retrieved_at=AW,
        )


def test_zero_eps_remains_valid() -> None:
    fact = ProviderFact(**_base_fact_kwargs(value=0.0))
    assert fact.value == 0.0


def test_negative_eps_remains_valid() -> None:
    fact = ProviderFact(**_base_fact_kwargs(value=-3.2))
    assert fact.value == -3.2


def test_zero_bvps_remains_valid() -> None:
    fact = ProviderFact(
        **_base_fact_kwargs(
            field_name=FinancialField.BVPS,
            provider_field="bookValue",
            value=0.0,
        )
    )
    assert fact.value == 0.0


def test_negative_bvps_remains_valid() -> None:
    fact = ProviderFact(
        **_base_fact_kwargs(
            field_name=FinancialField.BVPS,
            provider_field="bookValue",
            value=-1.5,
        )
    )
    assert fact.value == -1.5


def test_zero_common_shares_outstanding_rejected() -> None:
    with pytest.raises(ValueError, match="common_shares_outstanding"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.COMMON_SHARES_OUTSTANDING,
            value=0.0,
            units=FinancialUnit.SHARES,
            provider_id="sec_edgar",
            provider_field="us-gaap:CommonStockSharesOutstanding",
            retrieved_at=AW,
        )


def test_negative_preferred_shares_outstanding_rejected() -> None:
    with pytest.raises(ValueError, match="preferred_shares_outstanding"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.PREFERRED_SHARES_OUTSTANDING,
            value=-1.0,
            units=FinancialUnit.SHARES,
            provider_id="sec_edgar",
            provider_field="us-gaap:PreferredStockSharesOutstanding",
            retrieved_at=AW,
        )


# ===========================================================================
# ProviderFact — unit/field mismatch
# ===========================================================================


def test_eps_with_percentage_points_rejected() -> None:
    with pytest.raises(ValueError, match="units"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.EPS,
            value=5.0,
            units=FinancialUnit.PERCENTAGE_POINTS,
            provider_id="yfinance",
            provider_field="trailingEps",
            retrieved_at=AW,
        )


def test_aaa_yield_with_currency_per_share_rejected() -> None:
    with pytest.raises(ValueError, match="units"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.MACRO,
            subject_id="AAA",
            field_name=FinancialField.CURRENT_AAA_YIELD,
            value=4.4,
            units=FinancialUnit.CURRENCY_PER_SHARE,
            provider_id="fred",
            provider_field="FRED_AAA",
            retrieved_at=AW,
            currency="USD",
        )


# ===========================================================================
# ProviderFact — currency rules
# ===========================================================================


def test_per_share_requires_currency() -> None:
    with pytest.raises(ValueError, match="currency"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.EPS,
            value=5.0,
            units=FinancialUnit.CURRENCY_PER_SHARE,
            provider_id="yfinance",
            provider_field="trailingEps",
            retrieved_at=AW,
            currency=None,
        )


def test_currency_normalized_to_uppercase() -> None:
    fact = ProviderFact(**_base_fact_kwargs(currency=" usd "))
    assert fact.currency == "USD"


def test_blank_currency_rejected() -> None:
    with pytest.raises(ValueError, match="currency"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=FinancialField.EPS,
            value=5.0,
            units=FinancialUnit.CURRENCY_PER_SHARE,
            provider_id="yfinance",
            provider_field="trailingEps",
            retrieved_at=AW,
            currency="   ",
        )


def test_percentage_points_must_not_carry_currency() -> None:
    with pytest.raises(ValueError, match="currency"):
        ProviderFact(
            subject_kind=FinancialSubjectKind.MACRO,
            subject_id="AAA",
            field_name=FinancialField.CURRENT_AAA_YIELD,
            value=4.4,
            units=FinancialUnit.PERCENTAGE_POINTS,
            provider_id="fred",
            provider_field="FRED_AAA",
            retrieved_at=AW,
            currency="USD",
        )


# ===========================================================================
# ProviderFact — datetime invariants
# ===========================================================================


def test_naive_retrieved_at_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ProviderFact(**_base_fact_kwargs(retrieved_at=NAIVE))


def test_naive_observed_at_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ProviderFact(**_base_fact_kwargs(observed_at=NAIVE))


def test_naive_available_at_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ProviderFact(**_base_fact_kwargs(available_at=NAIVE))


def test_naive_period_start_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ProviderFact(
            **_base_fact_kwargs(
                observation_period_start=NAIVE,
                observation_period_end=PERIOD_END,
            )
        )


def test_reversed_observation_period_rejected() -> None:
    with pytest.raises(ValueError, match="observation_period_start"):
        ProviderFact(
            **_base_fact_kwargs(
                observation_period_start=PERIOD_END,
                observation_period_end=PERIOD_START,
            )
        )


def test_valid_observation_period() -> None:
    fact = ProviderFact(
        **_base_fact_kwargs(
            observation_period_start=PERIOD_START,
            observation_period_end=PERIOD_END,
        )
    )
    assert fact.observation_period_start == PERIOD_START
    assert fact.observation_period_end == PERIOD_END


def test_valid_completed_annual_capex_metadata() -> None:
    fact = ProviderFact(
        **_base_fact_kwargs(
            field_name=FinancialField.CAPITAL_EXPENDITURES,
            value=-25.0,
            units=FinancialUnit.CURRENCY,
            currency="usd",
            basis="fiscal_year",
            observation_period_start=PERIOD_START,
            observation_period_end=PERIOD_END,
            fiscal_year=2025,
            period_kind=PeriodKind.COMPLETED_ANNUAL,
            accounting_scope=AccountingScope.CONSOLIDATED,
            capital_expenditure_sign=CapitalExpenditureSign.NEGATIVE_CASH_OUTFLOW,
            provider_fact_id="  capex-2025  ",
        )
    )
    assert fact.fiscal_year == 2025
    assert fact.provider_fact_id == "capex-2025"
    assert fact.currency == "USD"


def test_fiscal_year_requires_completed_annual_period_kind() -> None:
    with pytest.raises(ValueError, match="completed_annual"):
        ProviderFact(**_base_fact_kwargs(fiscal_year=2025, period_kind=PeriodKind.QUARTERLY))


def test_nonpositive_fiscal_year_rejected() -> None:
    with pytest.raises(ValueError, match="positive year label"):
        ProviderFact(**_base_fact_kwargs(fiscal_year=0, period_kind=PeriodKind.COMPLETED_ANNUAL))


def test_capex_sign_rejected_for_non_capex_fact() -> None:
    with pytest.raises(ValueError, match="only applicable"):
        ProviderFact(
            **_base_fact_kwargs(
                capital_expenditure_sign=CapitalExpenditureSign.POSITIVE_EXPENDITURE,
            )
        )


# ===========================================================================
# ProviderFact — provider id/field validation
# ===========================================================================


def test_provider_id_canonicalized() -> None:
    fact = ProviderFact(**_base_fact_kwargs(provider_id="  YFinance  "))
    assert fact.provider_id == "yfinance"


def test_empty_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        ProviderFact(**_base_fact_kwargs(provider_id="   "))


def test_empty_provider_field_rejected() -> None:
    with pytest.raises(ValueError, match="provider_field"):
        ProviderFact(**_base_fact_kwargs(provider_field="   "))


def test_provider_fact_frozen() -> None:
    fact = ProviderFact(**_base_fact_kwargs())
    with pytest.raises(AttributeError):
        fact.value = 99.0  # type: ignore[misc]


def test_provider_fact_has_no_resolver_state() -> None:
    """ProviderFact must not expose resolver/cache fields."""
    fact = ProviderFact(**_base_fact_kwargs())
    for attr in ("source_kind", "origin_source_kind", "resolved_at", "cache_schema_version"):
        assert not hasattr(fact, attr), f"ProviderFact unexpectedly exposes {attr!r}"


# ===========================================================================
# FinancialFactsProvider — protocol conformance
# ===========================================================================


class _FakeProvider:
    """Tiny in-test fake provider (no reusable fixture dataset)."""

    def __init__(self, facts: tuple[ProviderFact, ...]) -> None:
        self._facts = facts

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        del request
        return self._facts


def _sample_eps_fact() -> ProviderFact:
    return ProviderFact(**_base_fact_kwargs())


def test_fake_structurally_satisfies_protocol() -> None:
    fake = _FakeProvider(())
    assert isinstance(fake, FinancialFactsProvider)


def test_fake_returns_tuple_of_facts() -> None:
    fact = _sample_eps_fact()
    fake = _FakeProvider((fact, fact))
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.EPS,
        provider_id="yfinance",
    )
    result = fake.fetch_facts(req)
    assert result == (fact, fact)
    assert all(isinstance(f, ProviderFact) for f in result)


def test_empty_tuple_represents_unavailable_not_zero() -> None:
    fake = _FakeProvider(())
    req = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.CURRENT_PRICE,
        provider_id="yfinance",
    )
    result = fake.fetch_facts(req)
    assert result == ()
    assert isinstance(result, tuple)
    assert len(result) == 0


def test_valuation_provider_error_distinct() -> None:
    with pytest.raises(FinancialProviderError):
        raise FinancialProviderError("provider transport failure")


def test_valuation_provider_error_is_exception() -> None:
    assert issubclass(FinancialProviderError, Exception)
