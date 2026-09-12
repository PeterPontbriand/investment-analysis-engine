"""Request-scoped, fail-open reporting of enforced data-quality decisions."""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from src.data.quality import QualityDecision, QualityOutcome

logger = logging.getLogger(__name__)
type QualityObserver = Callable[[QualityDecision], None]
_observer: ContextVar[QualityObserver | None] = ContextVar("quality_observer", default=None)


@contextmanager
def quality_observer(observer: QualityObserver) -> Iterator[None]:
    """Bind an observer to this execution context and restore it on exit."""
    token = _observer.set(observer)
    try:
        yield
    finally:
        _observer.reset(token)


def publish_quality(decisions: tuple[QualityDecision, ...]) -> None:
    """Retain candidate rejection evidence without presenting it as a run failure.

    A rejected cache entry or provider candidate may be replaced successfully.
    Execution boundaries report unrecovered failures to users; observers and
    debug logs retain individual decisions independently of the final outcome.
    """
    observer = _observer.get()
    for decision in decisions:
        if decision.outcome is not QualityOutcome.FAIL:
            continue
        logger.debug("Data quality rejected an input (%s).", decision.rule_id)
        if observer is not None:
            try:
                observer(decision)
            except Exception:
                logger.debug("Data quality observer failed.", exc_info=True)
