"""
Centralized domain constants and localization registry.

This module provides strongly-typed constants for financial data agents, including:
- Locale-specific translations (en/fr)
- Market trend status vectors
- Configuration key namespaces
- Standardized DataFrame column definitions

Classes:
    LocaleDictionary(TypedDict): Dictionary structure for locale-based translations.
    TrendStatus(str, Enum): Strongly-typed market trend indicators.
    ConfigKeys: Namespace for configuration key lookups.
    DataColumns: Standardized pandas DataFrame column definitions.
"""

from enum import StrEnum
from typing import Final, Literal, TypedDict


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


class ConfigKeys:
    """
    Namespace for configuration key lookups in pyproject.toml.

    Attributes:
        DEFAULT_SECTION: Section name for default settings.
        TICKER: Default ticker lookup key.

    """

    DEFAULT_SECTION: Final[str] = "default"
    TICKER: Final[str] = "default_ticker"


class DataColumns:
    """
    Standardized DataFrame column definitions for schema validation.

    Attributes:
        CLOSE: Closing price column.

    """

    CLOSE: Final[str] = "Close"
