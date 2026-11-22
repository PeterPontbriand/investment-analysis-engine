"""The one rule from a recorded provider failure to the status of the run it stopped, and the rule validators apply."""

import itertools

import pytest

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import (
    provider_failure_fits_status,
    provider_failure_of,
    provider_record_fits_status,
    provider_stopped_status,
    provider_stopped_status_of_record,
)
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.reporting.provider_messages import no_data_message

_OTHER_KINDS = (
    ProviderFailureKind.UNREACHABLE,
    ProviderFailureKind.RATE_LIMITED,
    ProviderFailureKind.UNEXPECTED_RESPONSE,
)


def _record(
    kind: ProviderFailureKind,
    *,
    provider_id: str = "yfinance",
    own_message: str | None = None,
    ticker_unlisted: bool = False,
) -> ProviderFailureRecord:
    return ProviderFailureRecord(
        kind=kind,
        provider_id=provider_id,
        input="historical_close",
        own_message=own_message,
        ticker_unlisted=ticker_unlisted,
    )


def test_a_run_whose_failed_inputs_are_all_no_data_is_an_unavailable_input() -> None:
    failure = provider_failure_of((_record(ProviderFailureKind.NO_DATA), _record(ProviderFailureKind.NO_DATA)))

    assert provider_stopped_status(failure) is CalculationStatus.INPUT_UNAVAILABLE


@pytest.mark.parametrize("other", _OTHER_KINDS)
def test_a_run_with_any_other_kind_among_the_failed_inputs_stays_a_provider_error(
    other: ProviderFailureKind,
) -> None:
    for records in itertools.permutations((_record(ProviderFailureKind.NO_DATA), _record(other))):
        assert provider_stopped_status(provider_failure_of(records)) is CalculationStatus.PROVIDER_ERROR


@pytest.mark.parametrize("other", _OTHER_KINDS)
def test_the_code_of_a_mixed_run_is_the_highest_precedence_kind_not_no_data(other: ProviderFailureKind) -> None:
    failure = provider_failure_of((_record(ProviderFailureKind.NO_DATA), _record(other)))

    assert failure is not None
    assert failure.reason_code.value == f"provider_{other.value}"


def test_a_failure_the_adapter_did_not_classify_is_a_provider_error() -> None:
    assert provider_stopped_status(None) is CalculationStatus.PROVIDER_ERROR
    assert provider_stopped_status_of_record(None) is CalculationStatus.PROVIDER_ERROR


def test_the_status_of_one_record_is_the_status_of_its_element() -> None:
    assert (
        provider_stopped_status_of_record(_record(ProviderFailureKind.NO_DATA)) is CalculationStatus.INPUT_UNAVAILABLE
    )
    for kind in _OTHER_KINDS:
        assert provider_stopped_status_of_record(_record(kind)) is CalculationStatus.PROVIDER_ERROR


@pytest.mark.parametrize("status", [CalculationStatus.PROVIDER_ERROR, CalculationStatus.INPUT_UNAVAILABLE])
def test_a_status_with_no_failure_element_always_fits(status: CalculationStatus) -> None:
    assert provider_failure_fits_status(status, None)
    assert provider_record_fits_status(status, None)


@pytest.mark.parametrize(
    ("kind", "status", "fits"),
    [
        (ProviderFailureKind.NO_DATA, CalculationStatus.INPUT_UNAVAILABLE, True),
        (ProviderFailureKind.NO_DATA, CalculationStatus.PROVIDER_ERROR, False),
        *[(kind, CalculationStatus.PROVIDER_ERROR, True) for kind in _OTHER_KINDS],
        *[(kind, CalculationStatus.INPUT_UNAVAILABLE, False) for kind in _OTHER_KINDS],
    ],
)
def test_a_failure_fits_the_status_its_code_gives_and_no_other(
    kind: ProviderFailureKind, status: CalculationStatus, fits: bool
) -> None:
    record = _record(kind)

    assert provider_record_fits_status(status, record) is fits
    assert provider_failure_fits_status(status, provider_failure_of((record,))) is fits


@pytest.mark.parametrize(
    "status",
    [
        CalculationStatus.OK,
        CalculationStatus.NOT_APPLICABLE,
        CalculationStatus.INVALID_INPUT,
    ],
)
@pytest.mark.parametrize("kind", list(ProviderFailureKind))
def test_every_other_status_has_no_failure_element(status: CalculationStatus, kind: ProviderFailureKind) -> None:
    assert not provider_record_fits_status(status, _record(kind))


def test_a_no_data_message_names_the_provider_and_what_it_returned_none_of() -> None:
    record = _record(ProviderFailureKind.NO_DATA)

    assert (
        no_data_message(record, what="price history", ticker="ZZZZQ")
        == "Yahoo Finance returned no price history for ZZZZQ."
    )


def test_a_no_data_message_for_a_ticker_absent_from_the_provider_list_names_the_list() -> None:
    record = _record(ProviderFailureKind.NO_DATA, provider_id="sec_edgar", ticker_unlisted=True)

    assert (
        no_data_message(record, what="annual filings", ticker="ZZZZQ")
        == "SEC EDGAR's ticker list does not include ZZZZQ."
    )


def test_a_no_data_message_the_adapter_wrote_to_be_shown_is_used_unchanged() -> None:
    own = "SEC's ticker file lists ZZZZQ under more than one CIK (1, 2); set an override."
    record = _record(ProviderFailureKind.NO_DATA, provider_id="sec_edgar", own_message=own)

    assert no_data_message(record, what="annual filings", ticker="ZZZZQ") == own


@pytest.mark.parametrize("kind", _OTHER_KINDS)
def test_a_no_data_message_refuses_another_kind(kind: ProviderFailureKind) -> None:
    with pytest.raises(ValueError, match="no_data"):
        no_data_message(_record(kind), what="price history", ticker="ZZZZQ")
