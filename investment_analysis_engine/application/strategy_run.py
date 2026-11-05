"""What a strategy's run function returns to the application: the run and how to present it."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.workspace.capture import ExecutionCapture


@dataclass(frozen=True)
class StrategyRun:
    """One strategy run: its normalized capture and how to present it.

    The strategy builds the two callables from its own presentation and presenter, so nothing outside the strategy
    knows what it presents. Both take the ``provider_check`` element, which is ``None`` when no provider is implicated.

    Attributes:
        execution: The normalized capture, which names the outcome and any recorded provider failure.
        document: Builds the strategy's typed document, as ``--json`` writes it.
        render_text: Renders the run in a text mode.
    """

    execution: ExecutionCapture
    document: Callable[[tuple[ProviderCheckItem, ...] | None], BaseModel]
    render_text: Callable[[tuple[ProviderCheckItem, ...] | None, TextPresentationMode], str]


__all__ = ["StrategyRun"]
