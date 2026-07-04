from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

# Type variable bound to a Pydantic Model for specific strategies
ConfigT = TypeVar("ConfigT", bound=BaseModel)


class BaseAnalyzer[ConfigT: BaseModel](ABC):
    """Abstract base class for all self-describing quantitative analysis strategies."""

    # Each subclass defines its own concrete parameter schema
    config_schema: type[ConfigT]

    def __init__(self, default_ticker: str | None = None) -> None:
        """Initialize the analyzer with an optional default ticker."""
        self.default_ticker = default_ticker

    @abstractmethod
    def run_analysis(self, config: ConfigT, ticker: str | None = None) -> Any:
        """Execute the structural strategy with validated parameters."""
        pass
