"""Tests for verified Step 2.3 production valuation adapters."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from src.analysis.graham_value.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.analysis.graham_value.models import CalculationStatus
from src.analysis.graham_value.provenance import SourceKind, ValuationSubjectKind
from src.analysis.graham_value.providers.massive import MASSIVE_PROVIDER_ID, MassiveValuationAdapter
from src.analysis.graham_value.providers.production import ProductionValuationProvider
from src.analysis.graham_value.providers.sec_edgar import (
    SEC_COMMON_SHARES_FIELD,
    SEC_PREFERRED_SHARES_FIELD,
    SEC_PROVIDER_ID,
    SEC_STOCKHOLDERS_EQUITY_FIELD,
    SecEdgarValuationAdapter,
)
from src.analysis.graham_value.resolver import InputResolver

NOW = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)


class FakeJsonFetcher:
    """URL-substring dispatcher that records calls and headers."""

    def __init__(self, routes: Mapping[str, object]) -> None:
        """Initialize the dispatcher with URL-substring response routes."""
        self.routes = dict(routes)
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        self.calls.append((url, dict(headers)))
        for marker, payload in self.routes.items():
            if marker in url:
                return payload
        msg = f"Unexpected URL: {url}"
        raise AssertionError(msg)


def _sec_request(*, as_of: datetime | None = None) -> ValuationFactRequest:
    return ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="aapl",
        field_name=ValuationField.EPS,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year",
        as_of=as_of,
        observation_count=3,
    )


def _sec_payload() -> dict[str, Any]:
    return {
        "facts": {
            "us-gaap": {
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            {
                                "start": "2022-09-25",
                                "end": "2023-09-30",
                                "val": 6.13,
                                "accn": "0001-23",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                            },
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "val": 6.08,
                                "accn": "0001-24",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-11-01",
                            },
                            # Restatement of FY2024 in a later amendment.  The
                            # adapter must pick the latest version knowable at
                            # the request boundary, not return an ambiguity.
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "val": 6.10,
                                "accn": "0001-24a",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K/A",
                                "filed": "2025-01-15",
                            },
                            {
                                "start": "2024-09-29",
                                "end": "2025-09-27",
                                "val": 7.00,
                                "accn": "0001-25",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-10-31",
                            },
                            # Quarterly observation must never enter the
                            # fiscal-year series.
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 2.0,
                                "accn": "0001-q1",
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-01",
                            },
                        ]
                    }
                }
            }
        }
    }


def _sec_payload_with_bvps_components(*, preferred_shares: float | None = 0.0) -> dict[str, Any]:
    payload = _sec_payload()
    us_gaap = payload["facts"]["us-gaap"]
    us_gaap["StockholdersEquity"] = {
        "units": {
            "USD": [
                {
                    "end": "2024-09-28",
                    "val": 60_000_000_000.0,
                    "accn": "0001-24",
                    "fy": 2024,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2024-11-01",
                },
                {
                    "end": "2025-09-27",
                    "val": 75_000_000_000.0,
                    "accn": "0001-25",
                    "fy": 2025,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2025-10-31",
                },
            ]
        }
    }
    us_gaap["CommonStockSharesOutstanding"] = {
        "units": {
            "shares": [
                {
                    "end": "2024-09-28",
                    "val": 15_000_000_000.0,
                    "accn": "0001-24",
                    "fy": 2024,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2024-11-01",
                },
                {
                    "end": "2025-09-27",
                    "val": 15_000_000_000.0,
                    "accn": "0001-25",
                    "fy": 2025,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2025-10-31",
                },
            ]
        }
    }
    if preferred_shares is not None:
        us_gaap["PreferredStockSharesOutstanding"] = {
            "units": {
                "shares": [
                    {
                        "end": "2024-09-28",
                        "val": 0.0,
                        "accn": "0001-24",
                        "fy": 2024,
                        "fp": "FY",
                        "form": "10-K",
                        "filed": "2024-11-01",
                    },
                    {
                        "end": "2025-09-27",
                        "val": preferred_shares,
                        "accn": "0001-25",
                        "fy": 2025,
                        "fp": "FY",
                        "form": "10-K",
                        "filed": "2025-10-31",
                    },
                ]
            }
        }
    return payload


def _submissions_payload() -> object:
    return {
        "filings": {
            "recent": {
                "accessionNumber": ["0001-23", "0001-24", "0001-24a", "0001-25"],
                "acceptanceDateTime": [
                    "2023-11-03T18:00:00Z",
                    "2024-11-01T18:00:00Z",
                    "2025-01-15T18:00:00Z",
                    "2025-10-31T18:00:00Z",
                ],
            }
        }
    }


def _sec_fetcher(company_facts: object | None = None) -> FakeJsonFetcher:
    return FakeJsonFetcher(
        {
            "company_tickers.json": {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}},
            "/companyfacts/": company_facts if company_facts is not None else _sec_payload(),
            "/submissions/": _submissions_payload(),
        }
    )


def _sec_component_request(field: ValuationField, *, as_of: datetime | None = None) -> ValuationFactRequest:
    return ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=field,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year_end",
        as_of=as_of,
    )


def test_sec_adapter_returns_one_annual_eps_fact_per_period_with_acceptance_provenance() -> None:
    fetcher = _sec_fetcher()
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)

    facts = adapter.fetch_facts(_sec_request())

    assert [fact.observation_period_end.year for fact in facts] == [2023, 2024, 2025]
    assert [fact.value for fact in facts] == pytest.approx([6.13, 6.10, 7.00])
    assert all(fact.provider_id == SEC_PROVIDER_ID for fact in facts)
    assert all(fact.provider_field == "us-gaap:EarningsPerShareDiluted" for fact in facts)
    assert all(fact.basis == "fiscal_year" for fact in facts)
    assert all(fact.currency == "USD" for fact in facts)
    assert facts[1].available_at == datetime(2025, 1, 15, 18, 0, tzinfo=UTC)
    assert "available_at uses EDGAR acceptanceDateTime" in facts[1].notes


def test_sec_adapter_historical_as_of_uses_restatement_known_at_boundary() -> None:
    fetcher = _sec_fetcher()
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)
    as_of = datetime(2024, 12, 31, 23, 59, tzinfo=UTC)

    facts = adapter.fetch_facts(_sec_request(as_of=as_of))

    # FY2025 and the Jan-2025 FY2024 amendment are both unavailable at as_of.
    assert [fact.observation_period_end.year for fact in facts] == [2023, 2024]
    assert facts[-1].value == pytest.approx(6.08)
    assert facts[-1].available_at == datetime(2024, 11, 1, 18, 0, tzinfo=UTC)


def test_sec_adapter_unsupported_capability_returns_empty_without_fetching() -> None:
    fetcher = _sec_fetcher()
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)
    request = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.BVPS,
        provider_id=SEC_PROVIDER_ID,
    )

    assert adapter.fetch_facts(request) == ()
    assert fetcher.calls == []


def test_sec_adapter_returns_bvps_components_with_exact_fields_and_period() -> None:
    fetcher = _sec_fetcher(_sec_payload_with_bvps_components())
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)

    equity = adapter.fetch_facts(_sec_component_request(ValuationField.STOCKHOLDERS_EQUITY))
    common = adapter.fetch_facts(_sec_component_request(ValuationField.COMMON_SHARES_OUTSTANDING))
    preferred = adapter.fetch_facts(_sec_component_request(ValuationField.PREFERRED_SHARES_OUTSTANDING))

    assert len(equity) == len(common) == len(preferred) == 1
    assert equity[0].provider_field == SEC_STOCKHOLDERS_EQUITY_FIELD
    assert common[0].provider_field == SEC_COMMON_SHARES_FIELD
    assert preferred[0].provider_field == SEC_PREFERRED_SHARES_FIELD
    assert equity[0].units is ValuationUnit.CURRENCY
    assert common[0].units is ValuationUnit.SHARES
    assert preferred[0].value == pytest.approx(0.0)
    assert {fact.observation_period_end for fact in (equity[0], common[0], preferred[0])} == {
        datetime(2025, 9, 27, 23, 59, 59, 999999, tzinfo=UTC)
    }
    assert all(
        fact.available_at == datetime(2025, 10, 31, 18, 0, tzinfo=UTC) for fact in (equity[0], common[0], preferred[0])
    )


def test_sec_component_historical_as_of_uses_latest_period_known_at_boundary() -> None:
    fetcher = _sec_fetcher(_sec_payload_with_bvps_components())
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)
    as_of = datetime(2024, 12, 31, 23, 59, tzinfo=UTC)

    facts = adapter.fetch_facts(_sec_component_request(ValuationField.STOCKHOLDERS_EQUITY, as_of=as_of))

    assert len(facts) == 1
    assert facts[0].value == pytest.approx(60_000_000_000.0)
    assert facts[0].observation_period_end == datetime(2024, 9, 28, 23, 59, 59, 999999, tzinfo=UTC)
    assert facts[0].available_at == datetime(2024, 11, 1, 18, 0, tzinfo=UTC)


def test_sec_component_ambiguous_latest_share_class_values_are_unavailable() -> None:
    payload = _sec_payload_with_bvps_components()
    shares = payload["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["shares"]
    shares.append(
        {
            "end": "2025-09-27",
            "val": 5_000_000_000.0,
            "accn": "0001-25",
            "fy": 2025,
            "fp": "FY",
            "form": "10-K",
            "filed": "2025-10-31",
        }
    )
    fetcher = _sec_fetcher(payload)
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)

    assert adapter.fetch_facts(_sec_component_request(ValuationField.COMMON_SHARES_OUTSTANDING)) == ()


def test_resolver_derives_bvps_only_with_explicit_zero_preferred_share_guard() -> None:
    fetcher = _sec_fetcher(_sec_payload_with_bvps_components())
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)
    resolver = InputResolver(provider=adapter, clock=lambda: NOW)
    request = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.BVPS,
        provider_id=SEC_PROVIDER_ID,
    )

    result = resolver.resolve_bvps(request)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.value == pytest.approx(5.0)
    assert result.resolved_input.source_kind is SourceKind.DERIVED
    assert result.resolved_input.lineage is not None
    assert {component.field_name for component in result.resolved_input.lineage.components} == {
        ValuationField.STOCKHOLDERS_EQUITY.value,
        ValuationField.PREFERRED_SHARES_OUTSTANDING.value,
        ValuationField.COMMON_SHARES_OUTSTANDING.value,
    }


def test_resolver_historical_bvps_uses_components_known_at_as_of() -> None:
    fetcher = _sec_fetcher(_sec_payload_with_bvps_components())
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)
    resolver = InputResolver(provider=adapter, clock=lambda: NOW)
    as_of = datetime(2024, 12, 31, 23, 59, tzinfo=UTC)
    request = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.BVPS,
        provider_id=SEC_PROVIDER_ID,
        as_of=as_of,
    )

    result = resolver.resolve_bvps(request)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.value == pytest.approx(4.0)
    assert result.resolved_input.as_of == as_of
    assert result.resolved_input.observation_period_end == datetime(2024, 9, 28, 23, 59, 59, 999999, tzinfo=UTC)
    assert result.resolved_input.available_at == datetime(2024, 11, 1, 18, 0, tzinfo=UTC)


@pytest.mark.parametrize("preferred_shares", [None, 1_000_000.0])
def test_resolver_bvps_missing_or_nonzero_preferred_share_guard_is_unavailable(
    preferred_shares: float | None,
) -> None:
    fetcher = _sec_fetcher(_sec_payload_with_bvps_components(preferred_shares=preferred_shares))
    adapter = SecEdgarValuationAdapter(json_fetcher=fetcher, clock=lambda: NOW)
    resolver = InputResolver(provider=adapter, clock=lambda: NOW)
    request = ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.BVPS,
        provider_id=SEC_PROVIDER_ID,
    )

    result = resolver.resolve_bvps(request)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.resolved_input is None


def _massive_currency_payload() -> object:
    return {
        "status": "OK",
        "results": [
            {
                "ticker": "AAPL",
                "currency_name": "usd",
                "market": "stocks",
                "active": True,
            }
        ],
    }


def _massive_ttm_payload() -> object:
    return {
        "status": "OK",
        "results": [
            {
                "tickers": ["AAPL"],
                "cik": "0000320193",
                "timeframe": "trailing_twelve_months",
                "period_end": "2026-06-27",
                "filing_date": "2026-07-31",
                "diluted_earnings_per_share": 7.25,
            }
        ],
    }


def _massive_trade_payload() -> object:
    return {
        "status": "OK",
        "results": {
            "T": "AAPL",
            "p": 250.50,
            "i": "trade-123",
            "x": 4,
            "t": 1787331600000000000,
            "y": 1787331599000000000,
        },
    }


def _massive_fetcher() -> FakeJsonFetcher:
    return FakeJsonFetcher(
        {
            "/v3/reference/tickers?": _massive_currency_payload(),
            "/stocks/financials/v1/income-statements?": _massive_ttm_payload(),
            "/v2/last/trade/": _massive_trade_payload(),
        }
    )


def _massive_request(
    field: ValuationField,
    *,
    basis: str | None = None,
    as_of: datetime | None = None,
) -> ValuationFactRequest:
    return ValuationFactRequest(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=field,
        provider_id=MASSIVE_PROVIDER_ID,
        basis=basis,
        as_of=as_of,
    )


def test_massive_ttm_eps_preserves_current_only_provenance_and_secret_stays_in_header() -> None:
    fetcher = _massive_fetcher()
    adapter = MassiveValuationAdapter(api_key="secret-key", json_fetcher=fetcher, clock=lambda: NOW)

    facts = adapter.fetch_facts(_massive_request(ValuationField.EPS, basis="ttm"))

    assert len(facts) == 1
    fact = facts[0]
    assert fact.value == pytest.approx(7.25)
    assert fact.provider_field == "diluted_earnings_per_share"
    assert fact.basis == "ttm"
    assert fact.currency == "USD"
    assert fact.observation_period_end == datetime(2026, 6, 27, 23, 59, 59, 999999, tzinfo=UTC)
    assert fact.available_at == datetime(2026, 7, 31, 23, 59, 59, 999999, tzinfo=UTC)
    assert any("not its original publication date" in note for note in fact.notes)
    assert all("secret-key" not in url for url, _headers in fetcher.calls)
    assert all(headers["Authorization"] == "Bearer secret-key" for _url, headers in fetcher.calls)


def test_massive_latest_trade_price_has_observation_timestamp_and_currency() -> None:
    fetcher = _massive_fetcher()
    adapter = MassiveValuationAdapter(api_key="secret-key", json_fetcher=fetcher, clock=lambda: NOW)

    facts = adapter.fetch_facts(_massive_request(ValuationField.CURRENT_PRICE))

    assert len(facts) == 1
    fact = facts[0]
    assert fact.value == pytest.approx(250.50)
    assert fact.provider_field == "results.p"
    assert fact.currency == "USD"
    assert fact.observed_at is not None
    assert fact.available_at == fact.observed_at
    assert "trade_id=trade-123" in fact.notes


def test_massive_historical_request_is_unavailable_without_network_call() -> None:
    fetcher = _massive_fetcher()
    adapter = MassiveValuationAdapter(api_key="secret-key", json_fetcher=fetcher, clock=lambda: NOW)
    request = _massive_request(
        ValuationField.EPS,
        basis="ttm",
        as_of=datetime(2025, 12, 31, 23, 59, tzinfo=UTC),
    )

    assert adapter.fetch_facts(request) == ()
    assert fetcher.calls == []


def test_massive_unsupported_bvps_is_unavailable_without_network_call() -> None:
    fetcher = _massive_fetcher()
    adapter = MassiveValuationAdapter(api_key="secret-key", json_fetcher=fetcher, clock=lambda: NOW)

    assert adapter.fetch_facts(_massive_request(ValuationField.BVPS)) == ()
    assert fetcher.calls == []


def test_massive_missing_api_key_is_unavailable_without_network_call() -> None:
    fetcher = _massive_fetcher()
    adapter = MassiveValuationAdapter(api_key="", json_fetcher=fetcher, clock=lambda: NOW)

    assert adapter.fetch_facts(_massive_request(ValuationField.CURRENT_PRICE)) == ()
    assert fetcher.calls == []


def test_massive_non_ok_response_is_provider_error() -> None:
    fetcher = FakeJsonFetcher(
        {
            "/v3/reference/tickers?": {
                "status": "ERROR",
                "error": "not authorized",
            }
        }
    )
    adapter = MassiveValuationAdapter(api_key="secret-key", json_fetcher=fetcher, clock=lambda: NOW)

    with pytest.raises(ValuationProviderError, match="non-OK status"):
        adapter.fetch_facts(_massive_request(ValuationField.CURRENT_PRICE))


class StaticProvider:
    """Tiny provider fake for router and assembly integration."""

    def __init__(self, facts: tuple[ProviderFact, ...]) -> None:
        """Initialize the fake with the facts it may return."""
        self.facts = facts
        self.calls: list[ValuationFactRequest] = []

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        self.calls.append(request)
        return tuple(
            fact
            for fact in self.facts
            if fact.provider_id == request.provider_id
            and fact.field_name is request.field_name
            and fact.basis == request.basis
        )


def _annual_eps_fact(value: float, year: int) -> ProviderFact:
    return ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.EPS,
        value=value,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=SEC_PROVIDER_ID,
        provider_field="us-gaap:EarningsPerShareDiluted",
        retrieved_at=NOW,
        basis="fiscal_year",
        currency="USD",
        observation_period_start=datetime(year - 1, 10, 1, tzinfo=UTC),
        observation_period_end=datetime(year, 9, 30, tzinfo=UTC),
        available_at=datetime(year, 11, 1, 18, 0, tzinfo=UTC),
    )


def _massive_quote_fact() -> ProviderFact:
    observed = datetime(2026, 8, 21, 17, 59, tzinfo=UTC)
    return ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=ValuationField.CURRENT_PRICE,
        value=250.5,
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=MASSIVE_PROVIDER_ID,
        provider_field="results.p",
        retrieved_at=NOW,
        currency="USD",
        observed_at=observed,
        available_at=observed,
    )


def test_production_provider_routes_without_rewriting_provider_identity() -> None:
    sec = StaticProvider((_annual_eps_fact(5.0, 2023),))
    massive = StaticProvider((_massive_quote_fact(),))
    provider = ProductionValuationProvider(sec_edgar=sec, massive=massive)

    sec_result = provider.fetch_facts(_sec_request())
    quote_result = provider.fetch_facts(_massive_request(ValuationField.CURRENT_PRICE))

    assert sec_result[0].provider_id == SEC_PROVIDER_ID
    assert quote_result[0].provider_id == MASSIVE_PROVIDER_ID


def test_graham_number_assembly_can_use_sec_eps_and_massive_quote() -> None:
    fetcher = _sec_fetcher(_sec_payload_with_bvps_components())
    sec = SecEdgarValuationAdapter(
        json_fetcher=fetcher,
        clock=lambda: NOW,
    )
    massive = StaticProvider((_massive_quote_fact(),))
    provider = ProductionValuationProvider(sec_edgar=sec, massive=massive)
    resolver = InputResolver(provider=provider, clock=lambda: NOW)

    result = resolver.assemble_graham_number(
        security_subject_id="AAPL",
        security_provider_id=SEC_PROVIDER_ID,
        quote_provider_id=MASSIVE_PROVIDER_ID,
    )

    assert result.status is CalculationStatus.OK
    assert result.eps is not None
    assert result.eps.value == pytest.approx(6.41)
    assert result.eps.source_kind is SourceKind.DERIVED
    assert result.eps.lineage is not None
    assert {component.provider_id for component in result.eps.lineage.components} == {SEC_PROVIDER_ID}
    assert result.bvps is not None
    assert result.bvps.value == pytest.approx(5.0)
    assert result.bvps.source_kind is SourceKind.DERIVED
    assert result.bvps.lineage is not None
    assert {component.provider_id for component in result.bvps.lineage.components} == {SEC_PROVIDER_ID}
    assert result.current_price is not None
    assert result.current_price.value == pytest.approx(250.5)
    assert result.current_price.provider_id == MASSIVE_PROVIDER_ID
    assert massive.calls[-1].field_name is ValuationField.CURRENT_PRICE
