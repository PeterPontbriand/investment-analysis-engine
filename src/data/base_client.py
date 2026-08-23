"""Abstract base layer defining data-fetching contracts for financial clients."""

from abc import ABC, abstractmethod

import pandas as pd


class DataFetchError(ValueError):
    """Custom domain-specific exception raised when market data retrieval fails.

    Inherits from ValueError to maintain backward-compatibility with existing
    error-handling boundaries and test assertions.
    """

    pass


class BaseDataClient(ABC):
    """Abstract Base Class (interface) that all concrete market data clients must implement."""

    @abstractmethod
    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        """Retrieve historical market data vector for a given asset ticker.

        Args:
            ticker: The target stock or asset ticker symbol.
            start_date: Query start date (format: YYYY-MM-DD).
            end_date: Optional query end date (format: YYYY-MM-DD).

        Returns:
            pd.DataFrame: A structured pandas DataFrame containing standard market indicators.

        Raises:
            DataFetchError: If retrieval fails, the asset is invalid, or the dataset is empty.
        """
        pass

    @abstractmethod
    def fetch_current_price(self, ticker: str) -> float:
        """Resolve the current market price (quote) for a given asset ticker.

        Current quotes are a first-class capability, distinct from the
        historical series downloaded via :meth:`fetch_data`.

        Args:
            ticker: The target stock or asset ticker symbol.

        Returns:
            float: The latest available price for the ticker.

        Raises:
            DataFetchError: If the quote cannot be resolved or is not positive.
        """
        pass
