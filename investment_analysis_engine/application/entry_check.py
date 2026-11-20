"""Adding entries to a watchlist, with a check that each ticker is one the data providers know.

The entries are added exactly as :func:`add_watchlist_entries` adds them. Only when that has succeeded is each distinct
ticker looked up, and a ticker that could not be confirmed gets a warning. The check never refuses an entry and never
turns a successful add into a failure.
"""

import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.instrument_profiles import lookup_instrument_profile
from investment_analysis_engine.application.watchlists import add_watchlist_entries
from investment_analysis_engine.core.entry_warnings import EntryWarning, not_checked_warning, not_recognized_warning
from investment_analysis_engine.core.failure_codes import FailureReasonCode, provider_reason_code
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.core.tickers import normalize_ticker
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError, storage_reason
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


def check_tickers(context: ApplicationContext, tickers: Sequence[str]) -> tuple[EntryWarning, ...]:
    """Look each distinct ticker up once, in order of first appearance, and return a warning for each unconfirmed one.

    After the first ``provider_unreachable``, ``provider_rate_limited`` or database failure (a readiness error or a raw
    storage error, classified as the readiness check classifies it) no further ticker is
    looked up: each remaining one is warned as not checked, with that failure's code. Any other failure the lookup
    raises propagates.
    """
    distinct = list(dict.fromkeys(normalize_ticker(ticker) for ticker in tickers))
    warnings: list[EntryWarning] = []
    stopped_by: FailureReasonCode | None = None
    for ticker in distinct:
        if stopped_by is not None:
            warnings.append(not_checked_warning(ticker, stopped_by))
            continue
        try:
            lookup_instrument_profile(context, ticker)
        except DataFetchError as exc:
            if exc.kind is ProviderFailureKind.NO_DATA:
                warnings.append(not_recognized_warning(ticker))
                continue
            code = provider_reason_code(exc.kind)
            warnings.append(not_checked_warning(ticker, code))
            if code in _STOPPING_CODES:
                stopped_by = code
        except DatabaseReadinessError as exc:
            stopped_by = exc.reason_code
            logger.error("The database was not ready while checking %s.", ticker, exc_info=exc)
            warnings.append(not_checked_warning(ticker, stopped_by))
        except (OSError, sqlite3.Error, SQLAlchemyError) as exc:
            stopped_by = FailureReasonCode(storage_reason(exc).value)
            logger.error("A storage error occurred while checking %s.", ticker, exc_info=exc)
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
    return AddedEntries(watchlist, check_tickers(context, [ticker for ticker, _ in entries]))


__all__ = ["AddedEntries", "add_watchlist_entries_checked", "check_tickers"]
