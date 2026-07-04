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
