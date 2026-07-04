"""
Centralized domain constants and localization registry.

This module provides strongly-typed constants for financial data agents, including:
- Locale-specific translations (en/fr)
- Market trend status vectors
- Order execution actions
- Configuration key namespaces
- Standardized DataFrame column definitions

Classes:
    LocaleDictionary(TypedDict): Dictionary structure for locale-based translations.
    TrendStatus(str, Enum): Strongly-typed market trend indicators.
    OrderAction(str, Enum): Execution side actions for portfolio tracking.
    ConfigKeys: Namespace for configuration key lookups.
    DataColumns: Standardized pandas DataFrame column definitions.
"""

from enum import StrEnum
from typing import Final, Literal, TypedDict


class AnalysisType(StrEnum):
    """
    Analysis types for financial data agents.

    Attributes:
        MOMENTUM: Momentum Indicator technical analysis

    """

    MOMENTUM = "momentum"
    # BOLLINGER_BAND = "bollinger-band" # Future expansion hook
    # VALUE = "value"                   # Future expansion hook
    # RSI = "rsi"                       # Future expansion hook
    # MEAN_REVERSION = "mean-reversion" # Future expansion hook


class LocaleDictionary(TypedDict):
    """
    Typed dictionary mapping locales to translation dictionaries.

    Example:
        {
            "en": {"BULLISH": "Bullish Trend", ...},
            "fr": {"BULLISH": "Tendance Haussière", ...}
        }

    Keys:
        en: English translations
        fr: French translations

    """

    en: dict[str, str]
    fr: dict[str, str]


class TrendStatus(StrEnum):
    """
    Strongly-typed market trend indicators with localization support.

    Attributes:
        BULLISH: Bullish market trend.
        BEARISH: Bearish market trend.
        UNKNOWN: Unknown or neutral market state.

    """

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    UNKNOWN = "UNKNOWN"

    def display_name(self, locale: str = "en") -> str:
        """
        Return localized display name for the trend status.

        Args:
            locale: Language code ("en" or "fr"). Defaults to "en".

        Returns:
            Localized string representation of the trend status.

        """
        translations: Final[LocaleDictionary] = {
            "en": {
                "BULLISH": "Bullish Trend",
                "BEARISH": "Bearish Trend",
                "UNKNOWN": "Unknown State",
            },
            "fr": {
                "BULLISH": "Tendance Haussière",
                "BEARISH": "Tendance Baissière",
                "UNKNOWN": "État Inconnu",
            },
        }
        # Narrow the dynamic string to a literal valid key to make mypy happy
        target_locale: Literal["en", "fr"] = "fr" if locale == "fr" else "en"
        locale_set = translations[target_locale]
        return locale_set.get(self.value, self.value)


class OrderAction(StrEnum):
    """
    Execution side actions for portfolio tracking and order submission.

    Attributes:
        BUY: Buy/Long position.
        SELL: Sell/Short position.
        HOLD: Hold/Flat position.

    """

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    def display_name(self, locale: str = "en") -> str:
        """
        Return localized display name for the order action.

        Args:
            locale: Language code ("en" or "fr"). Defaults to "en".

        Returns:
            Localized string representation of the order action.

        """
        translations: Final[LocaleDictionary] = {
            "en": {"BUY": "Buy / Long", "SELL": "Sell / Short", "HOLD": "Flat / Hold"},
            "fr": {"BUY": "Acheter", "SELL": "Vendre", "HOLD": "Conserver"},
        }
        # Narrow the dynamic string to a literal valid key to make mypy happy
        target_locale: Literal["en", "fr"] = "fr" if locale == "fr" else "en"
        locale_set = translations[target_locale]
        return locale_set.get(self.value, self.value)


class ConfigKeys:
    """
    Namespace for configuration key lookups in pyproject.toml.

    Attributes:
        DEFAULT_SECTION: Section name for default settings.
        TICKER: Default ticker lookup key.
        START_DATE: Data start date key.
        WINDOW_SIZES: Window sizes configuration key.
        SHORT_WINDOW: Short window size key.
        LONG_WINDOW: Long window size key.

    """

    DEFAULT_SECTION: Final[str] = "default"
    TICKER: Final[str] = "default_ticker"
    START_DATE: Final[str] = "data_start_date"
    WINDOW_SIZES: Final[str] = "window_sizes"
    SHORT_WINDOW: Final[str] = "short_window"
    LONG_WINDOW: Final[str] = "long_window"


class DataColumns:
    """
    Standardized DataFrame column definitions for schema validation.

    Attributes:
        CLOSE: Closing price column.
        SIGNAL: Signal data column.
        CROSSOVER: Crossover indicator column.

    """

    CLOSE: Final[str] = "Close"
    SIGNAL: Final[str] = "Signal"
    CROSSOVER: Final[str] = "Crossover"
