"""Tests for src.data.valuation.facts provider-neutral contracts.

Uses tiny in-test fakes only; no reusable fixture datasets.  All datetimes are
fixed timezone-aware values — no ``datetime.now()``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import inf, nan
from typing import Any

import pytest

from src.data.valuation.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationFactsProvider,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.data.valuation.provenance import ValuationSubjectKind

AW = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)  # aware
NAIVE = datetime(2025, 6, 1, 12, 0)  # naive
AS_OF = datetime(2025, 12, 31, tzinfo=UTC)
PERIOD_START = datetime(2024, 7, 1, tzinfo=UTC)
PERIOD_END = datetime(2025, 6, 30, tzinfo=UTC)


# ===========================================================================
# Enum members
# ===========================================================================


def test_valuation_field_members() -> None:
    assert ValuationField.CURRENT_PRICE.value == "current_price"
    assert ValuationField.EPS.value == "eps"
    assert ValuationField.BVPS.value == "bvps"
    assert ValuationField.CURRENT_AAA_YIELD.value == "current_aaa_yield"
    assert ValuationField.STOCKHOLDERS_EQUITY.value == "stockholders_equity"
    assert ValuationField.COMMON_SHARES_OUTSTANDING.value == "common_shares_outstanding"
    assert ValuationField.PREFERRED_SHARES_OUTSTANDING.value == "preferred_shares_outstanding"
    assert len(list(ValuationField)) == 7


def test_valuation_unit_members() -> None:
    assert ValuationUnit.CURRENCY_PER_SHARE.value == "currency_per_share"
    assert ValuationUnit.PERCENTAGE_POINTS.value == "percentage_points"
    assert ValuationUnit.CURRENCY.value == "currency"
    assert ValuationUnit.SHARES.value == "shares"
    assert len(list(ValuationUnit)) == 4


# ===========================================================================
# ValuationFactRequest — valid construction
# ===========================================================================


def test_valid_security_current_price_request() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.CURRENT_PRICE,
        provider_id="yfinance",
    )
    assert req.subject_kind is ValuationSubjectKind.SECURITY
    assert req.subject_id == "AAPL"
    assert req.field_name is ValuationField.CURRENT_PRICE
    assert req.provider_id == "yfinance"
    assert req.basis is None
    assert req.as_of is None
    assert req.observation_count == 1


def test_valid_security_eps_request() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.EPS,
        provider_id="yfinance",
        basis="ttm",
    )
    assert req.field_name is ValuationField.EPS
    assert req.basis == "ttm"


def test_valid_security_bvps_request() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="MSFT",
        field_name=ValuationField.BVPS,
        provider_id="yfinance",
    )
    assert req.field_name is ValuationField.BVPS


def test_valid_macro_aaa_yield_request() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="AAA",
        field_name=ValuationField.CURRENT_AAA_YIELD,
        provider_id="fred",
        as_of=AS_OF,
    )
    assert req.subject_kind is ValuationSubjectKind.MACRO
    assert req.field_name is ValuationField.CURRENT_AAA_YIELD
    assert req.as_of == AS_OF


# ===========================================================================
# ValuationFactRequest — normalization
# ===========================================================================


def test_security_symbol_normalization() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="  aapl  ",
        field_name=ValuationField.EPS,
        provider_id="yfinance",
    )
    assert req.subject_id == "AAPL"


def test_macro_id_case_preserved() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="  aaa  ",
        field_name=ValuationField.CURRENT_AAA_YIELD,
        provider_id="fred",
    )
    assert req.subject_id == "aaa"


def test_macro_id_uppercase_preserved() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="AAA",
        field_name=ValuationField.CURRENT_AAA_YIELD,
        provider_id="fred",
    )
    assert req.subject_id == "AAA"


def test_provider_id_canonicalization() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.EPS,
        provider_id="  YFinance  ",
    )
    assert req.provider_id == "yfinance"


# ===========================================================================
# ValuationFactRequest — rejection
# ===========================================================================


def test_request_empty_subject_id_rejected() -> None:
    with pytest.raises(ValueError, match="subject_id"):
        ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="   ",
            field_name=ValuationField.EPS,
            provider_id="yfinance",
        )


def test_request_empty_provider_id_rejected() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.EPS,
            provider_id="   ",
        )


def test_request_empty_basis_rejected() -> None:
    with pytest.raises(ValueError, match="basis"):
        ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.EPS,
            provider_id="yfinance",
            basis="   ",
        )


def test_request_naive_as_of_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.EPS,
            provider_id="yfinance",
            as_of=NAIVE,
        )


def test_request_zero_observation_count_rejected() -> None:
    with pytest.raises(ValueError, match="observation_count"):
        ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.EPS,
            provider_id="yfinance",
            observation_count=0,
        )


def test_request_negative_observation_count_rejected() -> None:
    with pytest.raises(ValueError, match="observation_count"):
        ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.EPS,
            provider_id="yfinance",
            observation_count=-3,
        )


def test_eps_multiple_observations_allowed() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.EPS,
        provider_id="yfinance",
        observation_count=3,
    )
    assert req.observation_count == 3


@pytest.mark.parametrize(
    "field_name",
    [
        ValuationField.CURRENT_PRICE,
        ValuationField.BVPS,
        ValuationField.CURRENT_AAA_YIELD,
        ValuationField.STOCKHOLDERS_EQUITY,
        ValuationField.COMMON_SHARES_OUTSTANDING,
        ValuationField.PREFERRED_SHARES_OUTSTANDING,
    ],
)
def test_multiple_observations_rejected_for_non_eps(field_name: ValuationField) -> None:
    subject_kind = (
        ValuationSubjectKind.MACRO if field_name is ValuationField.CURRENT_AAA_YIELD else ValuationSubjectKind.SECURITY
    )
    with pytest.raises(ValueError, match="observation_count"):
        ValuationFactRequest(
            subject_kind=subject_kind,
            subject_id="AAPL",
            field_name=field_name,
            provider_id="yfinance",
            observation_count=3,
        )


def test_aaa_yield_requires_macro() -> None:
    with pytest.raises(ValueError, match="MACRO"):
        ValuationFactRequest(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.CURRENT_AAA_YIELD,
            provider_id="yfinance",
        )


def test_security_field_requires_security() -> None:
    with pytest.raises(ValueError, match="SECURITY"):
        ValuationFactRequest(
            subject_kind=ValuationSubjectKind.MACRO,
            subject_id="AAA",
            field_name=ValuationField.EPS,
            provider_id="fred",
        )


def test_request_frozen() -> None:
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.EPS,
        provider_id="yfinance",
    )
    with pytest.raises(AttributeError):
        req.provider_id = "other"  # type: ignore[misc]


# ===========================================================================
# ProviderFact — valid construction
# ===========================================================================


def test_valid_current_price_fact() -> None:
    fact = ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.CURRENT_PRICE,
        value=210.5,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id="yfinance",
        provider_field="regularMarketPrice",
        retrieved_at=AW,
        currency="USD",
    )
    assert fact.value == 210.5
    assert fact.currency == "USD"


def test_valid_eps_fact() -> None:
    fact = ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.EPS,
        value=6.1,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id="yfinance",
        provider_field="trailingEps",
        retrieved_at=AW,
        basis="ttm",
        currency="USD",
    )
    assert fact.field_name is ValuationField.EPS
    assert fact.basis == "ttm"


def test_valid_bvps_fact() -> None:
    fact = ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="MSFT",
        field_name=ValuationField.BVPS,
        value=42.3,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id="yfinance",
        provider_field="bookValue",
        retrieved_at=AW,
        currency="USD",
    )
    assert fact.value == 42.3


def test_valid_aaa_yield_fact() -> None:
    fact = ProviderFact(
        subject_kind=ValuationSubjectKind.MACRO,
        subject_id="AAA",
        field_name=ValuationField.CURRENT_AAA_YIELD,
        value=4.4,
        units=ValuationUnit.PERCENTAGE_POINTS,
        provider_id="fred",
        provider_field="FRED_AAA",
        retrieved_at=AW,
    )
    assert fact.value == 4.4
    assert fact.currency is None


def test_valid_stockholders_equity_fact() -> None:
    fact = ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.STOCKHOLDERS_EQUITY,
        value=75_000_000_000.0,
        units=ValuationUnit.CURRENCY,
        provider_id="sec_edgar",
        provider_field="us-gaap:StockholdersEquity",
        retrieved_at=AW,
        basis="fiscal_year_end",
        currency="USD",
        observation_period_end=PERIOD_END,
    )
    assert fact.units is ValuationUnit.CURRENCY
    assert fact.currency == "USD"


def test_valid_common_shares_outstanding_fact() -> None:
    fact = ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.COMMON_SHARES_OUTSTANDING,
        value=15_000_000_000.0,
        units=ValuationUnit.SHARES,
        provider_id="sec_edgar",
        provider_field="us-gaap:CommonStockSharesOutstanding",
        retrieved_at=AW,
        basis="fiscal_year_end",
        observation_period_end=PERIOD_END,
    )
    assert fact.units is ValuationUnit.SHARES
    assert fact.currency is None


def test_zero_preferred_shares_outstanding_is_valid_guard_fact() -> None:
    fact = ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.PREFERRED_SHARES_OUTSTANDING,
        value=0.0,
        units=ValuationUnit.SHARES,
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
        "subject_kind": ValuationSubjectKind.SECURITY,
        "subject_id": "AAPL",
        "field_name": ValuationField.EPS,
        "value": 5.0,
        "units": ValuationUnit.CURRENCY_PER_SHARE,
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
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.CURRENT_PRICE,
            value=0.0,
            units=ValuationUnit.CURRENCY_PER_SHARE,
            provider_id="yfinance",
            provider_field="regularMarketPrice",
            retrieved_at=AW,
            currency="USD",
        )


def test_negative_current_price_rejected() -> None:
    with pytest.raises(ValueError, match="current_price"):
        ProviderFact(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.CURRENT_PRICE,
            value=-1.0,
            units=ValuationUnit.CURRENCY_PER_SHARE,
            provider_id="yfinance",
            provider_field="regularMarketPrice",
            retrieved_at=AW,
            currency="USD",
        )


def test_zero_aaa_yield_rejected() -> None:
    with pytest.raises(ValueError, match="current_aaa_yield"):
        ProviderFact(
            subject_kind=ValuationSubjectKind.MACRO,
            subject_id="AAA",
            field_name=ValuationField.CURRENT_AAA_YIELD,
            value=0.0,
            units=ValuationUnit.PERCENTAGE_POINTS,
            provider_id="fred",
            provider_field="FRED_AAA",
            retrieved_at=AW,
        )


def test_negative_aaa_yield_rejected() -> None:
    with pytest.raises(ValueError, match="current_aaa_yield"):
        ProviderFact(
            subject_kind=ValuationSubjectKind.MACRO,
            subject_id="AAA",
            field_name=ValuationField.CURRENT_AAA_YIELD,
            value=-2.0,
            units=ValuationUnit.PERCENTAGE_POINTS,
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
            field_name=ValuationField.BVPS,
            provider_field="bookValue",
            value=0.0,
        )
    )
    assert fact.value == 0.0


def test_negative_bvps_remains_valid() -> None:
    fact = ProviderFact(
        **_base_fact_kwargs(
            field_name=ValuationField.BVPS,
            provider_field="bookValue",
            value=-1.5,
        )
    )
    assert fact.value == -1.5


def test_zero_common_shares_outstanding_rejected() -> None:
    with pytest.raises(ValueError, match="common_shares_outstanding"):
        ProviderFact(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.COMMON_SHARES_OUTSTANDING,
            value=0.0,
            units=ValuationUnit.SHARES,
            provider_id="sec_edgar",
            provider_field="us-gaap:CommonStockSharesOutstanding",
            retrieved_at=AW,
        )


def test_negative_preferred_shares_outstanding_rejected() -> None:
    with pytest.raises(ValueError, match="preferred_shares_outstanding"):
        ProviderFact(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.PREFERRED_SHARES_OUTSTANDING,
            value=-1.0,
            units=ValuationUnit.SHARES,
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
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.EPS,
            value=5.0,
            units=ValuationUnit.PERCENTAGE_POINTS,
            provider_id="yfinance",
            provider_field="trailingEps",
            retrieved_at=AW,
        )


def test_aaa_yield_with_currency_per_share_rejected() -> None:
    with pytest.raises(ValueError, match="units"):
        ProviderFact(
            subject_kind=ValuationSubjectKind.MACRO,
            subject_id="AAA",
            field_name=ValuationField.CURRENT_AAA_YIELD,
            value=4.4,
            units=ValuationUnit.CURRENCY_PER_SHARE,
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
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.EPS,
            value=5.0,
            units=ValuationUnit.CURRENCY_PER_SHARE,
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
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id="AAPL",
            field_name=ValuationField.EPS,
            value=5.0,
            units=ValuationUnit.CURRENCY_PER_SHARE,
            provider_id="yfinance",
            provider_field="trailingEps",
            retrieved_at=AW,
            currency="   ",
        )


def test_percentage_points_must_not_carry_currency() -> None:
    with pytest.raises(ValueError, match="currency"):
        ProviderFact(
            subject_kind=ValuationSubjectKind.MACRO,
            subject_id="AAA",
            field_name=ValuationField.CURRENT_AAA_YIELD,
            value=4.4,
            units=ValuationUnit.PERCENTAGE_POINTS,
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
# ValuationFactsProvider — protocol conformance
# ===========================================================================


class _FakeProvider:
    """Tiny in-test fake provider (no reusable fixture dataset)."""

    def __init__(self, facts: tuple[ProviderFact, ...]) -> None:
        self._facts = facts

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:  # noqa: ARG002
        del request
        return self._facts


def _sample_eps_fact() -> ProviderFact:
    return ProviderFact(**_base_fact_kwargs())


def test_fake_structurally_satisfies_protocol() -> None:
    fake = _FakeProvider(())
    assert isinstance(fake, ValuationFactsProvider)


def test_fake_returns_tuple_of_facts() -> None:
    fact = _sample_eps_fact()
    fake = _FakeProvider((fact, fact))
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.EPS,
        provider_id="yfinance",
    )
    result = fake.fetch_facts(req)
    assert result == (fact, fact)
    assert all(isinstance(f, ProviderFact) for f in result)


def test_empty_tuple_represents_unavailable_not_zero() -> None:
    fake = _FakeProvider(())
    req = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.CURRENT_PRICE,
        provider_id="yfinance",
    )
    result = fake.fetch_facts(req)
    assert result == ()
    assert isinstance(result, tuple)
    assert len(result) == 0


def test_valuation_provider_error_distinct() -> None:
    with pytest.raises(ValuationProviderError):
        raise ValuationProviderError("provider transport failure")


def test_valuation_provider_error_is_exception() -> None:
    assert issubclass(ValuationProviderError, Exception)
