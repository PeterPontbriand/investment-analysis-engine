"""Abstract base layer defining data-fetching contracts for financial clients."""

from abc import ABC, abstractmethod

import pandas as pd

from src.data.market_data import HistoricalMarketData, MarketDataContext, latest_observation_date


class DataFetchError(ValueError):
    """Custom domain-specific exception raised when market data retrieval fails.

    Inherits from ValueError to maintain backward-compatibility with existing
    error-handling boundaries and test assertions.
    """

    pass


class BaseDataClient(ABC):
    """Abstract Base Class (interface) that all concrete market data clients must implement."""

    @property
    def provider_id(self) -> str | None:
        """Return the stable market-data provider identity when the client retains one.

        Provider identity is execution/presentation context, not part of the
        strategy calculation result. Clients that do not retain a stable
        identity leave it unavailable rather than forcing callers to guess.
        """
        return None

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

    def fetch_data_with_context(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
    ) -> HistoricalMarketData:
        """Retrieve historical data together with context known by the base boundary.

        Concrete clients may override this method to retain provider-specific
        metadata such as observation interval, currency, or price-adjustment basis. The default path
        never guesses those fields.
        """
        frame = self.fetch_data(ticker, start_date, end_date)
        context = MarketDataContext(
            provider_id=self.provider_id,
            data_as_of=latest_observation_date(frame),
            observation_count=len(frame),
        )
        return HistoricalMarketData(frame=frame, context=context)

    def fetch_historical_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
    ) -> HistoricalMarketData:
        """Satisfy the provider-neutral historical market-data boundary."""
        return self.fetch_data_with_context(ticker, start_date, end_date)

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
