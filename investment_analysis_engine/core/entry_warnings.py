"""The warnings that adding entries to a watchlist can give about a ticker, and their messages.

Adding an entry never refuses a ticker the providers do not know: the entry is added and the ticker gets one warning.
The warning codes are an open set of their own, separate from the failure reason codes: a new code is an addition. A
warning has the shape of a rule error: a ``template`` with each value written as ``{argument}``, the ``arguments`` and
the ``message``, which is the template with every placeholder filled.

This is a leaf module: it imports only ``investment_analysis_engine.core`` and the standard library.
"""

from collections.abc import Mapping, Sequence
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

    TICKER_NOT_IN_SEC_LIST = "ticker_not_in_sec_list"
    """The ticker was recognized, but SEC EDGAR's ticker list does not include it, so the strategies of the new
    entries that read SEC filings will be unavailable for it."""


ENTRY_WARNING_CODE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        EntryWarningCode.TICKER_NOT_RECOGNIZED.value: "entry-warning-ticker-not-recognized",
        EntryWarningCode.TICKER_NOT_CHECKED.value: "entry-warning-ticker-not-checked",
        EntryWarningCode.TICKER_NOT_IN_SEC_LIST.value: "entry-warning-ticker-not-in-sec-list",
    }
)
"""The glossary term that explains each warning code."""

_TICKER_ARGUMENT: Final = "ticker"
_STRATEGIES_ARGUMENT: Final = "strategies"

_NOT_RECOGNIZED_TEMPLATE: Final = (
    "No data provider recognizes {ticker}. Check the ticker, and remove the entry if it is wrong."
)
_UNREACHABLE_TEMPLATE: Final = "{ticker} could not be checked, because the data providers could not be reached."
_RATE_LIMITED_TEMPLATE: Final = (
    "{ticker} could not be checked, because a data provider asked the engine to wait before asking again."
)
_DATABASE_TEMPLATE: Final = "{ticker} could not be checked, because the engine's database was not available."
_UNEXPECTED_TEMPLATE: Final = "{ticker} could not be checked, because a data provider gave an unexpected answer."

_NOT_IN_SEC_LIST_TEMPLATE: Final = (
    "{ticker} is not in SEC EDGAR's ticker list, so {strategies} will be unavailable for it: they read the company's "
    "financial statements from SEC filings. SEC EDGAR lists a company only under its US ticker symbol, so a ticker on "
    "an exchange outside the United States is not in the list even when the company files with the SEC."
)

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
        template: The message with each value written as ``{argument}``.
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


def join_labels(labels: Sequence[str]) -> str:
    """Return the labels as ``A``, ``A and B`` or ``A, B and C``, in the order given."""
    if len(labels) < 2:
        return "".join(labels)
    return f"{', '.join(labels[:-1])} and {labels[-1]}"


def not_in_sec_list_warning(ticker: str, strategy_labels: Sequence[str]) -> EntryWarning:
    """Return the warning for a recognized ticker that SEC EDGAR's ticker list does not include.

    Args:
        ticker: The normalized ticker.
        strategy_labels: The labels of the strategies of the new entries that read SEC filings; each appears once, and
            the warning names them in the order of first appearance.

    Raises:
        ValueError: If no strategy label is given.
    """
    labels = list(dict.fromkeys(strategy_labels))
    if not labels:
        raise ValueError("The warning names at least one strategy.")
    arguments = {_TICKER_ARGUMENT: ticker, _STRATEGIES_ARGUMENT: join_labels(labels)}
    return EntryWarning(
        ticker,
        EntryWarningCode.TICKER_NOT_IN_SEC_LIST,
        None,
        _NOT_IN_SEC_LIST_TEMPLATE,
        arguments,
        fill_template(_NOT_IN_SEC_LIST_TEMPLATE, arguments),
    )


__all__ = [
    "ENTRY_WARNING_CODE_TERMS",
    "EntryWarning",
    "EntryWarningCode",
    "fill_template",
    "join_labels",
    "not_checked_warning",
    "not_in_sec_list_warning",
    "not_recognized_warning",
]
