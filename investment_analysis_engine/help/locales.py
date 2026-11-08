"""The locales the help bundle and the API's engine text are available in.

Each declared locale has one bundle file, ``help_bundle.<tag>.json``, named with the tag as declared. A tag is declared
in conventional BCP 47 case, such as ``en``, ``pt-BR`` or ``zh-Hant``, and tags are unique ignoring case. Matching a
request is case-insensitive, and the negotiated tag, which ``Content-Language`` states, is the declared form.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Locale:
    """One available locale.

    Attributes:
        tag: The locale's language tag in canonical lowercase form.
        name: The locale's name in its own language, which a language picker shows.
    """

    tag: str
    name: str


LOCALES: Final[tuple[Locale, ...]] = (Locale("en", "English"),)
"""Every available locale, in the order a picker lists them."""

DEFAULT_LOCALE: Final = "en"
"""The tag of the locale used when a request names none that is available."""


__all__ = ["DEFAULT_LOCALE", "LOCALES", "Locale"]
