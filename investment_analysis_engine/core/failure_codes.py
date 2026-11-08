"""The stable failure vocabulary: reason codes, the category that follows from a code, and the provider mapping.

This is a leaf module: it imports only ``investment_analysis_engine.core`` and the standard library, so every layer that
raises, classifies, stores or reports a failure can depend on it without a cycle. A code is never renamed, repurposed or
removed within the public contract.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal

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
    NOT_AUTHENTICATED = "not_authenticated"
    HOST_NOT_ALLOWED = "host_not_allowed"
    ORIGIN_NOT_ALLOWED = "origin_not_allowed"
    ENDPOINT_NOT_FOUND = "endpoint_not_found"
    REFRESH_JOB_NOT_FOUND = "refresh_job_not_found"
    REFRESH_JOB_RUNNING = "refresh_job_running"
    PORT_UNAVAILABLE = "port_unavailable"
    HELP_TERM_NOT_FOUND = "help_term_not_found"
    HELP_DOCUMENT_NOT_FOUND = "help_document_not_found"


type FailureStatus = Literal["error", "input_unavailable"]

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


FAILURE_REASON_CODE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        FailureReasonCode.EXECUTION_ERROR.value: "failure-execution-error",
        FailureReasonCode.HISTORICAL_QUALITY.value: "failure-historical-quality",
        FailureReasonCode.PROVIDER_ERROR.value: "status-provider-error",
        FailureReasonCode.PROVIDER_UNREACHABLE.value: "provider-unreachable",
        FailureReasonCode.PROVIDER_RATE_LIMITED.value: "provider-rate-limited",
        FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE.value: "provider-unexpected-response",
        FailureReasonCode.PROVIDER_NO_DATA.value: "provider-no-data",
        FailureReasonCode.CONFIGURATION_ERROR.value: "failure-configuration-error",
        FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS.value: "failure-no-eligible-observations",
        FailureReasonCode.INVALID_INPUT.value: "status-invalid-input",
        FailureReasonCode.INVALID_PARAMETER.value: "failure-invalid-parameter",
        FailureReasonCode.DATABASE_UPGRADE_REQUIRED.value: "failure-database",
        FailureReasonCode.DATABASE_INCOMPATIBLE_SCHEMA.value: "failure-database",
        FailureReasonCode.DATABASE_BUSY.value: "failure-database",
        FailureReasonCode.DATABASE_PERMISSION_DENIED.value: "failure-database",
        FailureReasonCode.DATABASE_INVALID_FILE.value: "failure-database",
        FailureReasonCode.DATABASE_IO_ERROR.value: "failure-database",
        FailureReasonCode.DATABASE_RESOURCES_UNAVAILABLE.value: "failure-database",
        FailureReasonCode.DATABASE_INITIALIZATION_FAILED.value: "failure-database",
        FailureReasonCode.DATABASE_MIGRATION_FAILED.value: "failure-database",
        FailureReasonCode.INVALID_STORED_RUN.value: "failure-stored-data-unreadable",
        FailureReasonCode.UNSUPPORTED_RUN_VERSION.value: "failure-unsupported-run-version",
        FailureReasonCode.WATCHLIST_NOT_FOUND.value: "failure-not-found",
        FailureReasonCode.WATCHLIST_ENTRY_NOT_FOUND.value: "failure-not-found",
        FailureReasonCode.WATCHLIST_EMPTY.value: "failure-watchlist-empty",
        FailureReasonCode.WATCHLIST_NAME_CONFLICT.value: "failure-name-conflict",
        FailureReasonCode.ANALYSIS_RUN_NOT_FOUND.value: "failure-not-found",
        FailureReasonCode.STORED_SELECTION_UNREADABLE.value: "failure-stored-data-unreadable",
        FailureReasonCode.UNSUPPORTED_PROJECTION.value: "failure-stored-data-unreadable",
        FailureReasonCode.NOT_AUTHENTICATED.value: "failure-request-refused",
        FailureReasonCode.HOST_NOT_ALLOWED.value: "failure-request-refused",
        FailureReasonCode.ORIGIN_NOT_ALLOWED.value: "failure-request-refused",
        FailureReasonCode.ENDPOINT_NOT_FOUND.value: "failure-not-found",
        FailureReasonCode.REFRESH_JOB_NOT_FOUND.value: "failure-not-found",
        FailureReasonCode.REFRESH_JOB_RUNNING.value: "failure-refresh-running",
        FailureReasonCode.PORT_UNAVAILABLE.value: "failure-port-unavailable",
        FailureReasonCode.HELP_TERM_NOT_FOUND.value: "failure-not-found",
        FailureReasonCode.HELP_DOCUMENT_NOT_FOUND.value: "failure-not-found",
    }
)
"""The glossary term that explains each failure code; codes that differ only in detail share one term."""


FAILURE_STATUS_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "error": "failure-category-error",
        "input_unavailable": "status-input-unavailable",
    }
)
"""The glossary term that explains each failure category."""


__all__ = [
    "FAILURE_STATUS_TERMS",
    "FAILURE_REASON_CODE_TERMS",
    "INPUT_UNAVAILABLE_CODES",
    "PROVIDER_CODE_BY_KIND",
    "PROVIDER_FAILURE_CODES",
    "FailureReasonCode",
    "FailureStatus",
    "provider_reason_code",
    "status_for",
]
