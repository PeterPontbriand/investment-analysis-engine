"""The provider failure kind, the exceptions that carry it and the library-call helper."""

import pytest

from src.core.provider_failure_kind import ProviderFailureKind, require_provider_identity
from src.data.base_client import DataFetchError
from src.data.financial.facts import FinancialProviderError
from src.data.provider_failure import DEFECT, FailureRule, call_library, classify_library_exception


class _ThrottledError(Exception):
    """Stands in for a library's rate-limit type."""


class _ShapeError(Exception):
    """Stands in for a library's changed-response type."""


class _MissingError(Exception):
    """Stands in for a library's unknown-ticker type."""


class _MisuseError(Exception):
    """Stands in for a library's programming-error type."""


class _SubOfShapeError(_ShapeError):
    """A subtype that a later, wider rule would also match."""


_RULES = (
    FailureRule((_MisuseError,), DEFECT),
    FailureRule((_MissingError,), ProviderFailureKind.NO_DATA),
    FailureRule((_ShapeError,), ProviderFailureKind.UNEXPECTED_RESPONSE),
    FailureRule((_ThrottledError, OSError), ProviderFailureKind.UNREACHABLE),
)


def _raise(error: BaseException) -> None:
    raise error


def test_the_three_kinds_have_stable_values() -> None:
    assert {kind.value for kind in ProviderFailureKind} == {"unreachable", "unexpected_response", "no_data"}


@pytest.mark.parametrize("exception_type", [DataFetchError, FinancialProviderError])
def test_exceptions_carry_kind_and_provider_as_additive_attributes(
    exception_type: type[DataFetchError] | type[FinancialProviderError],
) -> None:
    plain = exception_type("message")
    assert (plain.kind, plain.provider_id) == (None, None)
    assert str(plain) == "message"

    typed = exception_type("message", kind=ProviderFailureKind.NO_DATA, provider_id="sec_edgar")
    assert (typed.kind, typed.provider_id) == (ProviderFailureKind.NO_DATA, "sec_edgar")

    with pytest.raises(ValueError, match="provider_id"):
        exception_type("message", kind=ProviderFailureKind.NO_DATA)
    with pytest.raises(ValueError, match="blank"):
        exception_type("message", provider_id="  ")


def test_existing_exception_types_keep_their_bases() -> None:
    assert issubclass(DataFetchError, ValueError)
    assert issubclass(FinancialProviderError, Exception)
    assert not issubclass(FinancialProviderError, ValueError)


def test_identity_check_accepts_no_kind_without_a_provider() -> None:
    require_provider_identity(None, None)
    require_provider_identity(None, "yfinance")


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (_MissingError(), ProviderFailureKind.NO_DATA),
        (_ShapeError(), ProviderFailureKind.UNEXPECTED_RESPONSE),
        (_ThrottledError(), ProviderFailureKind.UNREACHABLE),
        (TimeoutError(), ProviderFailureKind.UNREACHABLE),
        (RuntimeError("nobody listed this"), ProviderFailureKind.UNEXPECTED_RESPONSE),
    ],
)
def test_each_listed_type_maps_to_its_kind_and_an_unlisted_one_is_an_unexpected_response(
    error: BaseException, kind: ProviderFailureKind
) -> None:
    assert classify_library_exception(error, _RULES) is kind


def test_the_first_matching_rule_wins() -> None:
    rules = (
        FailureRule((_ShapeError,), ProviderFailureKind.UNEXPECTED_RESPONSE),
        FailureRule((_SubOfShapeError,), ProviderFailureKind.NO_DATA),
    )
    assert classify_library_exception(_SubOfShapeError(), rules) is ProviderFailureKind.UNEXPECTED_RESPONSE
    assert classify_library_exception(_SubOfShapeError(), tuple(reversed(rules))) is ProviderFailureKind.NO_DATA


def test_a_rule_can_be_narrowed_by_a_test() -> None:
    rules = (
        FailureRule((OSError,), ProviderFailureKind.NO_DATA, when=lambda error: getattr(error, "errno", None) == 2),
        FailureRule((OSError,), ProviderFailureKind.UNREACHABLE),
    )
    assert classify_library_exception(FileNotFoundError(2, "gone"), rules) is ProviderFailureKind.NO_DATA
    assert classify_library_exception(OSError(5, "io"), rules) is ProviderFailureKind.UNREACHABLE


def test_a_listed_defect_propagates_unchanged() -> None:
    misuse = _MisuseError("bad call")
    with pytest.raises(_MisuseError) as caught:
        call_library(lambda: _raise(misuse), rules=_RULES, provider_id="yfinance", message="Library call failed")
    assert caught.value is misuse


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (_MissingError("no such ticker"), ProviderFailureKind.NO_DATA),
        (_ShapeError("columns changed"), ProviderFailureKind.UNEXPECTED_RESPONSE),
        (_ThrottledError("429"), ProviderFailureKind.UNREACHABLE),
    ],
)
@pytest.mark.parametrize("error_type", [FinancialProviderError, DataFetchError])
def test_a_classified_exception_becomes_a_typed_failure_chained_to_its_cause(
    error: BaseException, kind: ProviderFailureKind, error_type: type[DataFetchError] | type[FinancialProviderError]
) -> None:
    with pytest.raises(error_type) as caught:
        call_library(
            lambda: _raise(error),
            rules=_RULES,
            provider_id="yfinance",
            message="Library call failed",
            error_type=error_type,
        )
    failure = caught.value
    assert isinstance(failure, DataFetchError | FinancialProviderError)
    assert (failure.kind, failure.provider_id) == (kind, "yfinance")
    assert failure.__cause__ is error
    assert str(failure).startswith("Library call failed: ")


def test_an_already_typed_failure_passes_through_unchanged() -> None:
    inner = FinancialProviderError("typed", kind=ProviderFailureKind.NO_DATA, provider_id="massive")
    with pytest.raises(FinancialProviderError) as caught:
        call_library(lambda: _raise(inner), rules=_RULES, provider_id="yfinance", message="Library call failed")
    assert caught.value is inner


def test_a_successful_call_returns_its_value() -> None:
    assert call_library(lambda: 42, rules=_RULES, provider_id="yfinance", message="unused") == 42
