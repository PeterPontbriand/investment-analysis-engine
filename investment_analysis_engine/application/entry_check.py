"""Adding entries to a watchlist, with a check that each ticker is one the data providers know.

The entries are added exactly as :func:`add_watchlist_entries` adds them. Only when that has succeeded is each distinct
ticker looked up, and a ticker that could not be confirmed gets a warning. A ticker that was identified gets a warning
too when SEC EDGAR's ticker list does not include it and a strategy of a new entry for it reads SEC filings. The check
never refuses an entry and never turns a successful add into a failure.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.instrument_profiles import lookup_instrument_profile
from investment_analysis_engine.application.providers import build_sec_edgar_adapter
from investment_analysis_engine.application.watchlists import add_watchlist_entries
from investment_analysis_engine.core.entry_warnings import (
    EntryWarning,
    not_checked_warning,
    not_in_sec_list_warning,
    not_recognized_warning,
)
from investment_analysis_engine.core.failure_codes import FailureReasonCode, provider_reason_code
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.core.tickers import normalize_ticker
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.repositories.database_errors import DatabaseError
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.strategy_wiring import sec_edgar_strategy_label
from investment_analysis_engine.workspace.runs import Watchlist
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from investment_analysis_engine.workspace.watchlists import WatchlistRef

_STOPPING_CODES = frozenset({FailureReasonCode.PROVIDER_UNREACHABLE, FailureReasonCode.PROVIDER_RATE_LIMITED})
"""The provider failures after which no further ticker is looked up; a database failure also stops the check."""

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@dataclass(frozen=True)
class AddedEntries:
    """The watchlist after an add, and a warning for each ticker that could not be confirmed.

    Attributes:
        watchlist: The watchlist with the new entries.
        warnings: One warning for each unconfirmed ticker, in order of first appearance; empty when every ticker was
            confirmed.
    """

    watchlist: Watchlist
    warnings: tuple[EntryWarning, ...]


def _sec_labels_by_ticker(entries: Sequence[tuple[str, AnalysisSelection]]) -> dict[str, list[str]]:
    """Return, for each ticker, the labels of the strategies of its entries that read SEC EDGAR, each once."""
    labels: dict[str, list[str]] = {}
    for ticker, selection in entries:
        label = sec_edgar_strategy_label(selection)
        found = labels.setdefault(normalize_ticker(ticker), [])
        if label is not None and label not in found:
            found.append(label)
    return labels


def _sec_adapter(context: ApplicationContext) -> SecEdgarFinancialFactsAdapter | None:
    """Return the SEC adapter, or ``None`` when no SEC identity is set up."""
    try:
        return build_sec_edgar_adapter(context)
    except AnalysisConfigurationError:
        return None


def _not_in_sec_list(
    adapter: SecEdgarFinancialFactsAdapter | None, ticker: str, labels: Sequence[str]
) -> EntryWarning | None:
    """Return the warning when SEC's list lacks the ticker; none when it lists it, cannot be asked or has no reader."""
    if adapter is None or not labels:
        return None
    try:
        listed = adapter.lists_ticker(ticker)
    except (DataFetchError, FinancialProviderError, DatabaseError) as exc:
        logger.warning("SEC EDGAR's ticker list could not be asked about %s.", ticker, exc_info=exc)
        return None
    return None if listed else not_in_sec_list_warning(ticker, labels)


def check_tickers(
    context: ApplicationContext, entries: Sequence[tuple[str, AnalysisSelection]]
) -> tuple[EntryWarning, ...]:
    """Look each distinct ticker up once, in order of first appearance, and return a warning for each unconfirmed one.

    After the first ``provider_unreachable``, ``provider_rate_limited`` or database failure (a :class:`DatabaseError`)
    no further ticker is looked up: each remaining one is warned as not checked, with that failure's code. Any other
    failure the lookup raises propagates.

    A ticker that was identified gets the ``ticker_not_in_sec_list`` warning when an SEC identity is set up, at least
    one of its entries reads SEC EDGAR, and SEC's ticker list, which is asked at most once for the whole check, lists
    no such ticker and no CIK override names it. A failure while asking gives no warning and does not stop the check.
    """
    sec_labels = _sec_labels_by_ticker(entries)
    distinct = list(dict.fromkeys(normalize_ticker(ticker) for ticker, _ in entries))
    adapter = _sec_adapter(context) if any(sec_labels.values()) else None
    warnings: list[EntryWarning] = []
    stopped_by: FailureReasonCode | None = None
    for ticker in distinct:
        if stopped_by is not None:
            warnings.append(not_checked_warning(ticker, stopped_by))
            continue
        try:
            lookup_instrument_profile(context, ticker)
            not_listed = _not_in_sec_list(adapter, ticker, sec_labels[ticker])
            if not_listed is not None:
                warnings.append(not_listed)
        except DataFetchError as exc:
            if exc.kind is ProviderFailureKind.NO_DATA:
                warnings.append(not_recognized_warning(ticker))
                continue
            code = provider_reason_code(exc.kind)
            warnings.append(not_checked_warning(ticker, code))
            if code in _STOPPING_CODES:
                stopped_by = code
        except DatabaseError as exc:
            stopped_by = exc.reason_code
            logger.error("The database was not ready while checking %s.", ticker, exc_info=exc)
            warnings.append(not_checked_warning(ticker, stopped_by))
    return tuple(warnings)


def add_watchlist_entries_checked(
    context: ApplicationContext, ref: WatchlistRef, entries: Sequence[tuple[str, AnalysisSelection]]
) -> AddedEntries:
    """Add the entries as :func:`add_watchlist_entries` does, then check each distinct ticker.

    Every refusal of the add happens before any provider is asked. The entries stay stored whatever the warnings.

    Raises:
        Whatever :func:`add_watchlist_entries` raises.
    """
    watchlist = add_watchlist_entries(context, ref, entries)
    return AddedEntries(watchlist, check_tickers(context, entries))


__all__ = ["AddedEntries", "add_watchlist_entries_checked", "check_tickers"]
