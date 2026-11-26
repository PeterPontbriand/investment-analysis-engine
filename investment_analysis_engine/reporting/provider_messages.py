"""The reason message of a run a provider failure stopped, written once for every strategy.

A provider that answered and has nothing (a ``no_data`` failure) is reported in the provider's display name and says
only what the provider returned, never that the ticker does not exist. A ``no_data`` failure whose adapter wrote its
own message to be shown (it names the SEC override file) uses that message unchanged, found by the typed
``own_message`` of the failure record, never by reading text. A failure that says the provider's ticker list does not
include the ticker (``ticker_unlisted``) says so; for SEC EDGAR it also names the input that needed the company
identifier and says SEC lists companies under their US ticker symbols only. The messages of the other kinds stay with
the strategy that writes them.
"""

from typing import Final

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.reporting.presentation import provider_display_name

_INPUT_LABELS: Final = {
    "eps": "earnings per share",
    "bvps": "book value per share",
    "anchor_year_end": "annual report filings",
    "current_aaa_yield": "AAA corporate bond yield",
    "current_price": "share price",
}
"""How an input is named in a message when its name alone would be shorthand."""

_UNNAMED_INPUT: Final = "the company's financial statements"
"""What SEC EDGAR's unlisted-ticker message says could not be read when the caller names no input."""


def input_label(input_name: str) -> str:
    """Return an input's name as a message states it, without underscores or shorthand."""
    return _INPUT_LABELS.get(input_name, input_name.replace("_", " "))


def no_data_message(record: ProviderFailureRecord, *, what: str, ticker: str) -> str:
    """Return the reason of a run stopped by a ``no_data`` failure.

    Args:
        record: The failure; its kind is ``no_data``.
        what: What the provider returned none of, as a message states it, such as ``"price history"``; for SEC EDGAR's
            unlisted ticker, the input that needed the company identifier, such as ``"earnings per share"``; empty
            when the failure record names none, which that message words as "the company's financial statements".
        ticker: The ticker the run is for.

    Returns:
        The adapter's own message when it wrote one to be shown; when SEC EDGAR's ticker list does not include the
        ticker, ``"SEC EDGAR's ticker list does not include <ticker>, so <what> could not be read from SEC filings.
        SEC EDGAR lists companies under their US ticker symbols only."``; ``"<provider>'s ticker list does not
        include <ticker>."`` for another provider's list; else
        ``"<provider> returned no <what> for <ticker>."``.

    Raises:
        ValueError: If the record is not a ``no_data`` failure.
    """
    if record.kind is not ProviderFailureKind.NO_DATA:
        raise ValueError("A no-data message describes a no_data failure.")
    if record.own_message is not None:
        return record.own_message
    if record.ticker_unlisted and record.provider_id == SEC_PROVIDER_ID:
        read = what or _UNNAMED_INPUT
        return (
            f"{provider_display_name(record.provider_id)}'s ticker list does not include {ticker}, so {read} could not "
            "be read from SEC filings. SEC EDGAR lists companies under their US ticker symbols only."
        )
    if record.ticker_unlisted:
        return f"{provider_display_name(record.provider_id)}'s ticker list does not include {ticker}."
    return f"{provider_display_name(record.provider_id)} returned no {what} for {ticker}."


def is_no_data(record: ProviderFailureRecord | None) -> bool:
    """Return whether the failure is a classified ``no_data`` failure."""
    return record is not None and record.kind is ProviderFailureKind.NO_DATA


__all__ = ["input_label", "is_no_data", "no_data_message"]
