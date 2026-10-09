"""Classify a failure raised inside a third-party library call as one of the three provider failure kinds.

The helper wraps the library call only, never project code that reads its result. Each caller lists the exception
types it knows, in the order they are checked; the first rule that matches decides. A rule either names a kind or
marks the type a defect, which propagates unchanged. An exception no rule matches is an unexpected response, since
the service or the library did something the adapter did not expect.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from src.core.provider_failure_kind import ProviderFailureKind
from src.data.base_client import DataFetchError
from src.data.financial.facts import FinancialProviderError

DEFECT: Final = "defect"
"""The outcome of a rule whose exception types are programming errors and must propagate unchanged."""

Outcome = ProviderFailureKind | str


@dataclass(frozen=True)
class FailureRule:
    """Exception types, an optional narrowing test, and what a match means (a kind, or ``DEFECT``)."""

    types: tuple[type[BaseException], ...]
    outcome: Outcome
    when: Callable[[BaseException], bool] | None = None

    def matches(self, error: BaseException) -> bool:
        """Return whether *error* is one of the types and passes the test, if any."""
        return isinstance(error, self.types) and (self.when is None or self.when(error))


def classify_library_exception(error: BaseException, rules: Sequence[FailureRule]) -> Outcome:
    """Return the outcome of the first matching rule, or ``UNEXPECTED_RESPONSE`` when none matches."""
    for rule in rules:
        if rule.matches(error):
            return rule.outcome
    return ProviderFailureKind.UNEXPECTED_RESPONSE


def call_library[ResultT](
    call: Callable[[], ResultT],
    *,
    rules: Sequence[FailureRule],
    provider_id: str,
    message: str,
    error_type: type[DataFetchError] | type[FinancialProviderError] = FinancialProviderError,
) -> ResultT:
    """Run *call*; raise a typed provider failure for a classified exception and let a defect propagate.

    Args:
        call: A zero-argument callable that makes the third-party library call and nothing else.
        rules: The caller's exception rules, checked in order.
        provider_id: The provider the call serves.
        message: The sentence the raised failure starts with; the exception text follows it.
        error_type: The provider failure class to raise.

    Returns:
        Whatever *call* returns.

    Raises:
        DataFetchError | FinancialProviderError: Carrying the kind and *provider_id*, chained to the cause.
    """
    try:
        return call()
    except (DataFetchError, FinancialProviderError):
        raise
    except Exception as error:
        outcome = classify_library_exception(error, rules)
        if outcome == DEFECT:
            raise
        assert isinstance(outcome, ProviderFailureKind)
        raise error_type(f"{message}: {error}", kind=outcome, provider_id=provider_id) from error


__all__ = ["DEFECT", "FailureRule", "call_library", "classify_library_exception"]
