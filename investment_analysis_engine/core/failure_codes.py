"""The stable failure vocabulary: reason codes, the category that follows from a code, and the provider mapping.

This is a leaf module: it imports only ``investment_analysis_engine.core`` and the standard library, so every layer that
raises, classifies, stores or reports a failure can depend on it without a cycle. A code is never renamed, repurposed or
removed within the public contract.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind


class FailureReasonCode(StrEnum):
    """Stable failure categories a caller may branch on.

    A value is never renamed, repurposed or removed within the public contract. New values may be
    added, so a caller must treat an unrecognized value as a generic failure and use ``status`` for the
    category.
    """

    EXECUTION_ERROR = "execution_error"
    HISTORICAL_QUALITY = "historical_quality"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_UNEXPECTED_RESPONSE = "provider_unexpected_response"
    PROVIDER_NO_DATA = "provider_no_data"
    CONFIGURATION_ERROR = "configuration_error"
    NO_ELIGIBLE_OBSERVATIONS = "no_eligible_observations"
    INVALID_INPUT = "invalid_input"
    INVALID_PARAMETER = "invalid_parameter"
    DATABASE_UPGRADE_REQUIRED = "database_upgrade_required"
    DATABASE_INCOMPATIBLE_SCHEMA = "database_incompatible_schema"
    DATABASE_BUSY = "database_busy"
    DATABASE_PERMISSION_DENIED = "database_permission_denied"
    DATABASE_INVALID_FILE = "database_invalid_file"
    DATABASE_IO_ERROR = "database_io_error"
    DATABASE_RESOURCES_UNAVAILABLE = "database_resources_unavailable"
    DATABASE_INITIALIZATION_FAILED = "database_initialization_failed"
    DATABASE_MIGRATION_FAILED = "database_migration_failed"
    INVALID_STORED_RUN = "invalid_stored_run"
    UNSUPPORTED_RUN_VERSION = "unsupported_run_version"
    WATCHLIST_NOT_FOUND = "watchlist_not_found"
    WATCHLIST_ENTRY_NOT_FOUND = "watchlist_entry_not_found"
    WATCHLIST_EMPTY = "watchlist_empty"
    WATCHLIST_NAME_CONFLICT = "watchlist_name_conflict"
    ANALYSIS_RUN_NOT_FOUND = "analysis_run_not_found"
    STORED_SELECTION_UNREADABLE = "stored_selection_unreadable"
    UNSUPPORTED_PROJECTION = "unsupported_projection"


FailureStatus = Literal["error", "input_unavailable"]

PROVIDER_FAILURE_CODES = frozenset(
    {
        FailureReasonCode.PROVIDER_UNREACHABLE,
        FailureReasonCode.PROVIDER_RATE_LIMITED,
        FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE,
        FailureReasonCode.PROVIDER_NO_DATA,
    }
)

INPUT_UNAVAILABLE_CODES = frozenset(
    {
        FailureReasonCode.HISTORICAL_QUALITY,
        FailureReasonCode.PROVIDER_ERROR,
        FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS,
        *PROVIDER_FAILURE_CODES,
    }
)

# The one mapping from what an adapter observed to the stable code that reports it.
PROVIDER_CODE_BY_KIND: Mapping[ProviderFailureKind, FailureReasonCode] = MappingProxyType(
    {
        ProviderFailureKind.UNREACHABLE: FailureReasonCode.PROVIDER_UNREACHABLE,
        ProviderFailureKind.RATE_LIMITED: FailureReasonCode.PROVIDER_RATE_LIMITED,
        ProviderFailureKind.UNEXPECTED_RESPONSE: FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE,
        ProviderFailureKind.NO_DATA: FailureReasonCode.PROVIDER_NO_DATA,
    }
)


def status_for(code: FailureReasonCode) -> FailureStatus:
    """Return the category of a code: ``input_unavailable`` when the data could not be used, else ``error``."""
    return "input_unavailable" if code in INPUT_UNAVAILABLE_CODES else "error"


def provider_reason_code(kind: ProviderFailureKind | None) -> FailureReasonCode:
    """Return the code of a provider failure kind, or ``provider_error`` for a failure the adapter did not classify."""
    return FailureReasonCode.PROVIDER_ERROR if kind is None else PROVIDER_CODE_BY_KIND[kind]


__all__ = [
    "INPUT_UNAVAILABLE_CODES",
    "PROVIDER_CODE_BY_KIND",
    "PROVIDER_FAILURE_CODES",
    "FailureReasonCode",
    "FailureStatus",
    "provider_reason_code",
    "status_for",
]
