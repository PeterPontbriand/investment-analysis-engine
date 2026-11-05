"""Failures an application operation raises that its caller must tell apart from an ordinary exception.

A failure while an analysis result is being saved is raised as :class:`SavingFailureError`, so a caller can report that
the analysis finished and only the save failed. A defect (a stored selection that no longer converts, a blank ticker in
a refresh job) is an :class:`InternalDefectError`, which the failure classifier reports as an execution error.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import ClassVar

from pydantic import ValidationError

from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.workspace.capture import ExecutionCapture


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


__all__ = [
    "InternalDefectError",
    "SaveStage",
    "SavingFailureError",
    "require_job_ticker",
    "saving_failures",
    "stored_configuration",
]
