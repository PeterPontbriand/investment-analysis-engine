"""The failure code every classified exception reports, written out as literals.

This table is the reference for the classifier: it is not derived from the code under test, so a change to any
class's declared code, or to the classifier's fallbacks, fails a test that reads it. It was recorded from the
central rule table before each exception stated its own code, and it must keep its meaning across any change to
where or how a code is declared.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from investment_analysis_engine.cli_support import InternalDefectError
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError, InvalidParameterError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.market_data import (
    HistoricalMarketData,
    MarketDataContext,
    NoEligibleObservationsError,
)
from investment_analysis_engine.data.quality import (
    HistoricalDataQualityError,
    QualityContext,
    evaluate_historical_quality,
)
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError, ReadinessReason
from investment_analysis_engine.reporting.replay_inputs import UnsupportedProjectionError
from investment_analysis_engine.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError
from investment_analysis_engine.workspace.refresh import EmptyRefreshTargetError
from investment_analysis_engine.workspace.repositories.analysis_runs import AnalysisRunConflictError
from investment_analysis_engine.workspace.repositories.watchlists import (
    WatchlistConflictError,
    WatchlistEntryNotFoundError,
)
from investment_analysis_engine.workspace.watchlists import StoredSelectionError, WatchlistNotFoundError


@dataclass(frozen=True)
class PinnedClassification:
    """One exception instance and the code and status the classifier must report for it."""

    label: str
    exception_type: type[BaseException]
    build: Callable[[], BaseException]
    reason_code: str
    status: str


def _historical_quality_error() -> HistoricalDataQualityError:
    frame = pd.DataFrame({"Close": [1.0, float("nan")]}, index=pd.date_range("2026-09-09", periods=2))
    decisions = evaluate_historical_quality(
        HistoricalMarketData(frame, MarketDataContext()),
        context=QualityContext("ACME", datetime(2026, 9, 11, tzinfo=UTC)),
    )
    return HistoricalDataQualityError(decisions, frame)


def _plain(exception_type: type[BaseException]) -> Callable[[], BaseException]:
    return lambda: exception_type("x")


def _readiness(reason: ReadinessReason) -> Callable[[], BaseException]:
    return lambda: DatabaseReadinessError(reason, Path("x.sqlite3"))


def _provider(
    exception_type: type[DataFetchError] | type[FinancialProviderError], kind: ProviderFailureKind | None
) -> Callable[[], BaseException]:
    if kind is None:
        return lambda: exception_type("x")
    return lambda: exception_type("x", kind=kind, provider_id="p")


def _row(
    exception_type: type[BaseException], reason_code: str, status: str, *, label: str | None = None
) -> PinnedClassification:
    return PinnedClassification(
        label or exception_type.__name__, exception_type, _plain(exception_type), reason_code, status
    )


def _readiness_row(reason: ReadinessReason, reason_code: str) -> PinnedClassification:
    return PinnedClassification(
        f"DatabaseReadinessError[{reason.name}]", DatabaseReadinessError, _readiness(reason), reason_code, "error"
    )


def _provider_row(
    exception_type: type[DataFetchError] | type[FinancialProviderError],
    kind: ProviderFailureKind | None,
    reason_code: str,
) -> PinnedClassification:
    suffix = "no kind" if kind is None else kind.name
    return PinnedClassification(
        f"{exception_type.__name__}[{suffix}]",
        exception_type,
        _provider(exception_type, kind),
        reason_code,
        "input_unavailable",
    )


PINNED_CLASSIFICATIONS: tuple[PinnedClassification, ...] = (
    PinnedClassification(
        "HistoricalDataQualityError",
        HistoricalDataQualityError,
        _historical_quality_error,
        "historical_quality",
        "input_unavailable",
    ),
    _row(AnalysisConfigurationError, "configuration_error", "error"),
    _row(NoEligibleObservationsError, "no_eligible_observations", "input_unavailable"),
    PinnedClassification(
        "InvalidParameterError",
        InvalidParameterError,
        lambda: InvalidParameterError("x", parameters=("--x",)),
        "invalid_parameter",
        "error",
    ),
    _row(UnsupportedRunVersionError, "unsupported_run_version", "error"),
    _row(InvalidStoredRunError, "invalid_stored_run", "error"),
    _row(UnsupportedProjectionError, "unsupported_projection", "error"),
    _row(StoredSelectionError, "stored_selection_unreadable", "error"),
    _row(WatchlistNotFoundError, "watchlist_not_found", "error"),
    _row(EmptyRefreshTargetError, "watchlist_empty", "error"),
    _row(WatchlistEntryNotFoundError, "watchlist_entry_not_found", "error"),
    _row(WatchlistConflictError, "watchlist_name_conflict", "error"),
    _row(AnalysisRunConflictError, "execution_error", "error"),
    _row(InternalDefectError, "execution_error", "error"),
    _readiness_row(ReadinessReason.UPGRADE_REQUIRED, "database_upgrade_required"),
    _readiness_row(ReadinessReason.INCOMPATIBLE_SCHEMA, "database_incompatible_schema"),
    _readiness_row(ReadinessReason.BUSY, "database_busy"),
    _readiness_row(ReadinessReason.PERMISSION_DENIED, "database_permission_denied"),
    _readiness_row(ReadinessReason.INVALID_FILE, "database_invalid_file"),
    _readiness_row(ReadinessReason.IO_ERROR, "database_io_error"),
    _readiness_row(ReadinessReason.RESOURCES_UNAVAILABLE, "database_resources_unavailable"),
    _readiness_row(ReadinessReason.INITIALIZATION_FAILED, "database_initialization_failed"),
    _readiness_row(ReadinessReason.MIGRATION_FAILED, "database_migration_failed"),
    _provider_row(DataFetchError, None, "provider_error"),
    _provider_row(DataFetchError, ProviderFailureKind.UNREACHABLE, "provider_unreachable"),
    _provider_row(DataFetchError, ProviderFailureKind.RATE_LIMITED, "provider_rate_limited"),
    _provider_row(DataFetchError, ProviderFailureKind.UNEXPECTED_RESPONSE, "provider_unexpected_response"),
    _provider_row(DataFetchError, ProviderFailureKind.NO_DATA, "provider_no_data"),
    _provider_row(FinancialProviderError, None, "provider_error"),
    _provider_row(FinancialProviderError, ProviderFailureKind.UNREACHABLE, "provider_unreachable"),
    _provider_row(FinancialProviderError, ProviderFailureKind.RATE_LIMITED, "provider_rate_limited"),
    _provider_row(FinancialProviderError, ProviderFailureKind.UNEXPECTED_RESPONSE, "provider_unexpected_response"),
    _provider_row(FinancialProviderError, ProviderFailureKind.NO_DATA, "provider_no_data"),
    _row(ValueError, "invalid_input", "error"),
    _row(RuntimeError, "execution_error", "error"),
    _row(Exception, "execution_error", "error"),
)
