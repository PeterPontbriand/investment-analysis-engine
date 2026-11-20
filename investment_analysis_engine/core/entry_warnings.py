"""The warnings that adding entries to a watchlist can give about a ticker, and their messages.

Adding an entry never refuses a ticker the providers do not know: the entry is added and the ticker gets one warning.
The two warning codes are a closed set of their own, separate from the failure reason codes. A warning has the shape of
a rule error: a ``template`` with each value written as ``{argument}``, the ``arguments`` and the ``message``, which
is the template with every placeholder filled.

This is a leaf module: it imports only ``investment_analysis_engine.core`` and the standard library.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from investment_analysis_engine.core.failure_codes import FailureReasonCode


class EntryWarningCode(StrEnum):
    """Why a ticker added to a watchlist could not be confirmed; a value is never renamed or removed."""

    TICKER_NOT_RECOGNIZED = "ticker_not_recognized"
    """The data providers answered, and none of them identified the ticker."""

    TICKER_NOT_CHECKED = "ticker_not_checked"
    """The ticker could not be checked."""


ENTRY_WARNING_CODE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        EntryWarningCode.TICKER_NOT_RECOGNIZED.value: "entry-warning-ticker-not-recognized",
        EntryWarningCode.TICKER_NOT_CHECKED.value: "entry-warning-ticker-not-checked",
    }
)
"""The glossary term that explains each warning code."""

_TICKER_ARGUMENT: Final = "ticker"

_NOT_RECOGNIZED_TEMPLATE: Final = (
    "No data provider recognizes {ticker}. Check the ticker, and remove the entry if it is wrong."
)
_UNREACHABLE_TEMPLATE: Final = "{ticker} could not be checked, because the data providers could not be reached."
_RATE_LIMITED_TEMPLATE: Final = (
    "{ticker} could not be checked, because a data provider asked the engine to wait before asking again."
)
_DATABASE_TEMPLATE: Final = "{ticker} could not be checked, because the engine's database was not available."
_UNEXPECTED_TEMPLATE: Final = "{ticker} could not be checked, because a data provider gave an unexpected answer."

_NOT_CHECKED_TEMPLATES: Final[Mapping[FailureReasonCode, str]] = MappingProxyType(
    {
        FailureReasonCode.PROVIDER_UNREACHABLE: _UNREACHABLE_TEMPLATE,
        FailureReasonCode.PROVIDER_RATE_LIMITED: _RATE_LIMITED_TEMPLATE,
        FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE: _UNEXPECTED_TEMPLATE,
        FailureReasonCode.PROVIDER_ERROR: _UNEXPECTED_TEMPLATE,
    }
)
"""The template of each provider failure that leaves a ticker unchecked; a database failure has its own."""


@dataclass(frozen=True)
class EntryWarning:
    """One warning about one ticker.

    Attributes:
        ticker: The normalized ticker.
        code: Why the ticker could not be confirmed.
        reason_code: The failure reason code that kept the ticker from being checked; ``None`` when it was not
            recognized.
        template: The message with the ticker written as ``{ticker}``.
        arguments: The values the template shows, by placeholder name.
        message: The template with every placeholder filled.
    """

    ticker: str
    code: EntryWarningCode
    reason_code: FailureReasonCode | None
    template: str
    arguments: Mapping[str, str]
    message: str


def fill_template(template: str, arguments: Mapping[str, str]) -> str:
    """Return ``template`` with each ``{name}`` replaced by its argument, in a single pass."""
    out = template
    for name, value in arguments.items():
        out = out.replace(f"{{{name}}}", value)
    return out


def _warning(ticker: str, code: EntryWarningCode, reason_code: FailureReasonCode | None, template: str) -> EntryWarning:
    arguments = {_TICKER_ARGUMENT: ticker}
    return EntryWarning(ticker, code, reason_code, template, arguments, fill_template(template, arguments))


def not_recognized_warning(ticker: str) -> EntryWarning:
    """Return the warning for a ticker that the providers answered for and none identified."""
    return _warning(ticker, EntryWarningCode.TICKER_NOT_RECOGNIZED, None, _NOT_RECOGNIZED_TEMPLATE)


def not_checked_warning(ticker: str, reason_code: FailureReasonCode) -> EntryWarning:
    """Return the warning for a ticker that could not be checked, because of the failure ``reason_code``.

    A ``database_*`` code gives the database message; a provider code gives that failure's message.

    Raises:
        ValueError: If ``reason_code`` is neither a provider failure code nor a ``database_*`` code.
    """
    template = _NOT_CHECKED_TEMPLATES.get(reason_code)
    if template is None:
        if not reason_code.value.startswith("database_"):
            raise ValueError(f"{reason_code.value} is not a failure that leaves a ticker unchecked.")
        template = _DATABASE_TEMPLATE
    return _warning(ticker, EntryWarningCode.TICKER_NOT_CHECKED, reason_code, template)


__all__ = [
    "ENTRY_WARNING_CODE_TERMS",
    "EntryWarning",
    "EntryWarningCode",
    "fill_template",
    "not_checked_warning",
    "not_recognized_warning",
]
