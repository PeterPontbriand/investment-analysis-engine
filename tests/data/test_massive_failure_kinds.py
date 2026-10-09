"""Massive adapter: provider failure kinds."""

from collections.abc import Mapping
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.core.provider_failure_kind import ProviderFailureKind
from src.data.financial.facts import FinancialFactRequest, FinancialField, FinancialProviderError
from src.data.financial.provenance import FinancialSubjectKind
from src.data.massive.constants import MASSIVE_PROVIDER_ID
from src.data.massive.financial_facts import MassiveFinancialFactsAdapter

NOW = datetime(2026, 8, 29, 16, 0, tzinfo=UTC)


class _Fetcher:
    """Return one canned payload, or raise it, and record the keywords of each request."""

    def __init__(self, outcome: object) -> None:
        self._outcome = outcome
        self.calls: list[tuple[ProviderFailureKind, str]] = []

    def __call__(
        self, url: str, *, headers: Mapping[str, str], not_found: ProviderFailureKind, provider_id: str
    ) -> object:
        assert headers["Authorization"] == "Bearer secret-key"
        assert url
        self.calls.append((not_found, provider_id))
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


def _fetch(fetcher: _Fetcher) -> object:
    adapter = MassiveFinancialFactsAdapter(api_key="secret-key", json_fetcher=fetcher, clock=lambda: NOW)
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="AAPL",
        field_name=FinancialField.CURRENT_PRICE,
        provider_id=MASSIVE_PROVIDER_ID,
        basis=None,
        as_of=None,
    )
    return adapter.fetch_facts(request, effective_as_of=NOW)


def test_a_request_is_per_company_so_a_404_means_no_data_and_names_the_provider() -> None:
    fetcher = _Fetcher({"status": "OK", "results": []})
    _fetch(fetcher)
    assert fetcher.calls
    assert set(fetcher.calls) == {(ProviderFailureKind.NO_DATA, MASSIVE_PROVIDER_ID)}


def test_a_typed_transport_failure_passes_through_unchanged() -> None:
    outage = FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id=MASSIVE_PROVIDER_ID)
    with pytest.raises(FinancialProviderError) as caught:
        _fetch(_Fetcher(outage))
    assert caught.value is outage


@pytest.mark.parametrize("payload", [[], "text", {"status": "ERROR"}])
def test_an_answer_that_is_not_in_the_form_the_adapter_reads_is_an_unexpected_response(payload: object) -> None:
    with pytest.raises(FinancialProviderError) as caught:
        _fetch(_Fetcher(payload))
    assert (caught.value.kind, caught.value.provider_id) == (
        ProviderFailureKind.UNEXPECTED_RESPONSE,
        MASSIVE_PROVIDER_ID,
    )


@pytest.mark.parametrize("fault", [KeyError("k"), TypeError("t"), ValueError("v")])
def test_a_malformed_document_read_is_an_unexpected_response(fault: Exception) -> None:
    adapter_patch = patch.object(MassiveFinancialFactsAdapter, "_fetch_current_price", side_effect=fault)
    with adapter_patch, pytest.raises(FinancialProviderError) as caught:
        _fetch(_Fetcher({"status": "OK"}))
    assert caught.value.kind is ProviderFailureKind.UNEXPECTED_RESPONSE
    assert caught.value.__cause__ is fault


@pytest.mark.parametrize("defect", [RuntimeError("defect"), OSError("not a typed failure"), AttributeError("x")])
def test_a_non_provider_exception_inside_fetch_facts_propagates(defect: Exception) -> None:
    adapter_patch = patch.object(MassiveFinancialFactsAdapter, "_fetch_current_price", side_effect=defect)
    with adapter_patch, pytest.raises(type(defect)) as caught:
        _fetch(_Fetcher({"status": "OK"}))
    assert caught.value is defect
