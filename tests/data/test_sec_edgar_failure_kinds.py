"""SEC EDGAR adapter: provider failure kinds, and a missing CIK told apart from an unreachable ticker map."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from src.core.provider_failure_kind import ProviderFailureKind
from src.data.financial.facts import FinancialFactRequest, FinancialField, FinancialProviderError
from src.data.financial.provenance import FinancialSubjectKind
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter, _MissingCikError

NOW = datetime(2026, 8, 29, 16, 0, tzinfo=UTC)
_TICKER_ROWS = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}}
_COMPANY_FACTS = {"cik": 320193, "entityName": "Apple", "facts": {"us-gaap": {}}}
_UNREACHABLE = FinancialProviderError(
    "ticker map outage", kind=ProviderFailureKind.UNREACHABLE, provider_id=SEC_PROVIDER_ID
)


class _Fetcher:
    """Serve SEC documents, or raise per document kind, and record how each document was requested."""

    def __init__(self, **overrides: object) -> None:
        self.documents: dict[str, object] = {
            "company_tickers.json": _TICKER_ROWS,
            "/companyfacts/": _COMPANY_FACTS,
            "/submissions/": {"filings": {"recent": {}}},
        } | overrides
        self.calls: list[tuple[str, ProviderFailureKind, str]] = []

    def __call__(
        self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
    ) -> object:
        assert headers["User-Agent"]
        self.calls.append((url, not_found, provider_id))
        for marker, document in self.documents.items():
            if marker in url:
                if isinstance(document, BaseException):
                    raise document
                return document
        raise AssertionError(f"Unexpected SEC URL: {url}")


def _adapter(fetcher: _Fetcher) -> SecEdgarFinancialFactsAdapter:
    return SecEdgarFinancialFactsAdapter(json_fetcher=fetcher, clock=lambda: NOW, user_agent="Synthetic test")


def _request(field: FinancialField = FinancialField.EPS, ticker: str = "AAPL") -> FinancialFactRequest:
    balance_sheet = field in {
        FinancialField.STOCKHOLDERS_EQUITY,
        FinancialField.COMMON_SHARES_OUTSTANDING,
        FinancialField.PREFERRED_SHARES_OUTSTANDING,
    }
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=ticker,
        field_name=field,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year_end" if balance_sheet else "fiscal_year",
        as_of=None,
        observation_count=1,
    )


_FIELDS = [
    FinancialField.EPS,
    FinancialField.OPERATING_CASH_FLOW,
    FinancialField.CAPITAL_EXPENDITURES,
    FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
    FinancialField.STOCKHOLDERS_EQUITY,
]


def test_each_document_is_requested_with_its_own_404_kind_and_the_provider() -> None:
    fetcher = _Fetcher()
    _adapter(fetcher).create_analysis_snapshot(subject_id="AAPL", as_of=NOW)

    kinds = {
        ("company_tickers.json" in url, "/companyfacts/" in url, "/submissions/" in url): kind
        for url, kind, _ in fetcher.calls
    }
    assert kinds == {
        (True, False, False): ProviderFailureKind.UNEXPECTED_RESPONSE,
        (False, True, False): ProviderFailureKind.NO_DATA,
        (False, False, True): ProviderFailureKind.NO_DATA,
    }
    assert {provider for _, _, provider in fetcher.calls} == {SEC_PROVIDER_ID}


def test_a_ticker_with_no_cik_mapping_is_an_empty_snapshot() -> None:
    snapshot = _adapter(_Fetcher()).create_analysis_snapshot(subject_id="NOPE", as_of=NOW)
    assert snapshot.cik is None
    assert snapshot.company_facts == {}


@pytest.mark.parametrize("field", _FIELDS[:4])
def test_a_ticker_with_no_cik_mapping_has_no_facts_for_the_unavailable_when_unidentified_fields(
    field: FinancialField,
) -> None:
    assert _adapter(_Fetcher()).fetch_facts(_request(field, "NOPE"), effective_as_of=NOW) == ()


def test_a_ticker_with_no_cik_mapping_is_a_no_data_failure_for_the_other_fields() -> None:
    with pytest.raises(FinancialProviderError) as caught:
        _adapter(_Fetcher()).fetch_facts(_request(FinancialField.STOCKHOLDERS_EQUITY, "NOPE"), effective_as_of=NOW)
    assert (caught.value.kind, caught.value.provider_id) == (ProviderFailureKind.NO_DATA, SEC_PROVIDER_ID)


def test_a_ticker_map_outage_is_not_turned_into_an_empty_snapshot() -> None:
    adapter = _adapter(_Fetcher(**{"company_tickers.json": _UNREACHABLE}))
    with pytest.raises(FinancialProviderError) as caught:
        adapter.create_analysis_snapshot(subject_id="AAPL", as_of=NOW)
    assert caught.value is _UNREACHABLE


@pytest.mark.parametrize("field", _FIELDS)
def test_a_ticker_map_outage_is_not_turned_into_an_empty_fact_tuple(field: FinancialField) -> None:
    adapter = _adapter(_Fetcher(**{"company_tickers.json": _UNREACHABLE}))
    with pytest.raises(FinancialProviderError) as caught:
        adapter.fetch_facts(_request(field), effective_as_of=NOW)
    assert caught.value is _UNREACHABLE


def test_a_per_company_404_arrives_with_the_kind_the_transport_gave_it() -> None:
    missing = FinancialProviderError("404", kind=ProviderFailureKind.NO_DATA, provider_id=SEC_PROVIDER_ID)
    adapter = _adapter(_Fetcher(**{"/companyfacts/": missing}))
    with pytest.raises(FinancialProviderError) as caught:
        adapter.fetch_facts(_request(), effective_as_of=NOW)
    assert caught.value is missing


@pytest.mark.parametrize("name", ["company_tickers.json", "/companyfacts/", "/submissions/"])
@pytest.mark.parametrize("document", [[], "text", None])
def test_a_document_that_is_not_an_object_is_an_unexpected_response(name: str, document: object) -> None:
    adapter = _adapter(_Fetcher(**{name: document}))
    with pytest.raises(FinancialProviderError) as caught:
        adapter.fetch_facts(_request(), effective_as_of=NOW)
    assert (caught.value.kind, caught.value.provider_id) == (ProviderFailureKind.UNEXPECTED_RESPONSE, SEC_PROVIDER_ID)


@pytest.mark.parametrize("fault", [KeyError("missing"), TypeError("shape"), ValueError("value")])
def test_a_malformed_document_read_is_an_unexpected_response(fault: Exception) -> None:
    adapter = _adapter(_Fetcher())
    with (
        patch("src.data.sec_edgar.financial_facts._annual_eps_candidates", side_effect=fault),
        pytest.raises(FinancialProviderError) as caught,
    ):
        adapter.fetch_facts(_request(), effective_as_of=NOW)
    assert (caught.value.kind, caught.value.provider_id) == (ProviderFailureKind.UNEXPECTED_RESPONSE, SEC_PROVIDER_ID)
    assert caught.value.__cause__ is fault


@pytest.mark.parametrize("defect", [RuntimeError("defect"), OSError("not a typed failure"), AttributeError("x")])
def test_a_non_provider_exception_inside_fetch_facts_propagates(defect: Exception) -> None:
    adapter = _adapter(_Fetcher())
    with (
        patch("src.data.sec_edgar.financial_facts._annual_eps_candidates", side_effect=defect),
        pytest.raises(type(defect)) as caught,
    ):
        adapter.fetch_facts(_request(), effective_as_of=NOW)
    assert caught.value is defect


def test_the_private_missing_cik_condition_is_a_provider_failure_subclass() -> None:
    assert issubclass(_MissingCikError, FinancialProviderError)
    error: Any = _MissingCikError("x", kind=ProviderFailureKind.NO_DATA, provider_id=SEC_PROVIDER_ID)
    assert error.kind is ProviderFailureKind.NO_DATA
