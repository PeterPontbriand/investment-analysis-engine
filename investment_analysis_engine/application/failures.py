"""Failures an application operation raises that its caller must tell apart from an ordinary exception.

A failure while an analysis result is being saved is raised as :class:`SavingFailureError`, so a caller can report that
the analysis finished and only the save failed. A defect (a stored selection that no longer converts, a blank ticker in
a refresh job) is an :class:`InternalDefectError`, which the failure classifier reports as an execution error.

:func:`describe_failure` chooses the stable code and the one message shown for a failure; the direct commands and
the refresh operation share it.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import ClassVar

from pydantic import ValidationError

from investment_analysis_engine.core.failure_classification import classify_failure
from investment_analysis_engine.core.failure_codes import PROVIDER_FAILURE_CODES, FailureReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.workspace.capture import ExecutionCapture

logger = logging.getLogger(__name__)
# Without a configured handler (``--no-logging``) Python's last-resort handler would write the logged failure and its
# traceback to standard error; the null handler keeps standard error to the failure message alone.
logger.addHandler(logging.NullHandler())


class InternalDefectError(Exception):
    """A failure only a defect can cause, such as a stored selection that no longer converts to a configuration."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.EXECUTION_ERROR


def stored_configuration[ConfigT](convert: Callable[[], ConfigT]) -> ConfigT:
    """Return the configuration ``convert`` builds from a stored selection; a validation failure is a defect."""
    try:
        return convert()
    except ValidationError as exc:
        raise InternalDefectError("A stored selection no longer converts to a configuration.") from exc


def require_job_ticker(ticker: str) -> str:
    """Return ``ticker`` unchanged; a blank ticker in a refresh job is a defect."""
    if not ticker.strip():
        raise InternalDefectError("A refresh job has a blank ticker.")
    return ticker


class SaveStage:
    """Tells ``saving_failures`` whether the analysis has finished, so a later failure is a failure while saving."""

    def __init__(self, *, analyzed: bool = False) -> None:
        """Start before the analysis, or after it when ``analyzed`` is true."""
        self.analyzed = analyzed

    def after_analysis(self, capture: Callable[[], ExecutionCapture]) -> Callable[[], ExecutionCapture]:
        """Wrap ``capture`` so that the stage is marked analyzed once it has returned."""

        def marked() -> ExecutionCapture:
            result = capture()
            self.analyzed = True
            return result

        return marked


class SavingFailureError(Exception):
    """An exception raised after the analysis finished, while its result was saved; ``cause`` is the original."""

    def __init__(self, cause: Exception) -> None:
        """Keep the original exception."""
        super().__init__(str(cause))
        self.cause = cause


@contextmanager
def saving_failures(stage: SaveStage) -> Iterator[None]:
    """Re-raise an exception from the block as :class:`SavingFailureError` once ``stage`` says the analysis finished.

    An exception raised before the analysis finished passes through unchanged. A caller that exits with a
    control-flow exception of its own must not raise it inside the block.
    """
    try:
        yield
    except Exception as exc:
        if stage.analyzed:
            raise SavingFailureError(exc) from exc
        raise


# One message per kind of provider failure, then one for a failure the adapter did not classify. Each names the
# provider (when known) and the ticker, says what was observed, and offers no remedy.
_PROVIDER_FAILURE_MESSAGES = {
    ProviderFailureKind.UNREACHABLE: "Unable to analyze {subject}: {provider} did not serve the request.",
    ProviderFailureKind.RATE_LIMITED: "Unable to analyze {subject}: {provider} is limiting requests.",
    ProviderFailureKind.UNEXPECTED_RESPONSE: (
        "Unable to analyze {subject}: {provider} answered in a form the application does not read."
    ),
    ProviderFailureKind.NO_DATA: "Unable to analyze {subject}: {provider} returned no data for it.",
}
_UNCLASSIFIED_PROVIDER_FAILURE_MESSAGE = (
    "Unable to analyze {subject}: a data provider failed; the failure was not classified."
)


def provider_failure_message(error: DataFetchError | FinancialProviderError, ticker: str | None) -> str:
    """Return the message for a provider failure, from its kind, the provider that failed and the ticker."""
    subject = ticker or "the requested instrument"
    if error.kind is None:
        return _UNCLASSIFIED_PROVIDER_FAILURE_MESSAGE.format(subject=subject)
    return _PROVIDER_FAILURE_MESSAGES[error.kind].format(subject=subject, provider=error.provider_id)


# Failures whose own message was written to be shown: the quality, parameter and configuration messages, and the
# database messages (every code that starts with ``database_``). No other exception's text is shown.
_SHOWN_AS_RAISED = frozenset(
    {
        FailureReasonCode.HISTORICAL_QUALITY,
        FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS,
        FailureReasonCode.INVALID_PARAMETER,
        FailureReasonCode.CONFIGURATION_ERROR,
    }
)
_PROVIDER_CODES = frozenset({FailureReasonCode.PROVIDER_ERROR, *PROVIDER_FAILURE_CODES})


@dataclass(frozen=True)
class FailureDescription:
    """The code of a failure and the one message shown for it."""

    code: FailureReasonCode
    message: str


def describe_failure(exception: BaseException, ticker: str | None, *, saving: bool) -> FailureDescription:
    """Return the code and the message of a failure; the direct commands and refresh share this rule.

    The failure code chooses the message and no message names a strategy. A provider code gives
    :func:`provider_failure_message`; the codes in ``_SHOWN_AS_RAISED`` and every ``database_*`` code show the
    exception's own text; ``invalid_input`` and ``execution_error`` each have one fixed message. A failure while the
    analysis result is being saved (``saving``) has the save message and the code it classifies to. Any other code
    is reported as ``execution_error``. Wherever a fixed message replaces the exception's text, the exception is
    logged with its traceback.

    Args:
        exception: The failure.
        ticker: The ticker the job or command resolved, or ``None`` before one was.
        saving: Whether the analysis had finished and its result was being saved.

    Returns:
        The code and the message.
    """
    code = classify_failure(exception).reason_code
    subject = ticker or "the requested instrument"
    if saving:
        message = f"{ticker or 'The requested instrument'} was analyzed, but the result could not be saved."
    elif code in _PROVIDER_CODES and isinstance(exception, DataFetchError | FinancialProviderError):
        message = provider_failure_message(exception, ticker)
    elif code.value.startswith("database_") or code in _SHOWN_AS_RAISED:
        return FailureDescription(code=code, message=str(exception))
    elif code is FailureReasonCode.INVALID_INPUT:
        message = f"Unable to analyze {subject}: invalid analysis inputs or provider data."
    else:
        code = FailureReasonCode.EXECUTION_ERROR
        message = f"Unable to analyze {subject}: the analysis failed unexpectedly."
    logger.error("Failure reported to the user as: %s", message, exc_info=exception)
    return FailureDescription(code=code, message=message)


__all__ = [
    "FailureDescription",
    "InternalDefectError",
    "SaveStage",
    "SavingFailureError",
    "describe_failure",
    "provider_failure_message",
    "require_job_ticker",
    "saving_failures",
    "stored_configuration",
]
