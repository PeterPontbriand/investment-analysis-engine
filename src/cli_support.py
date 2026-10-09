"""Shared CLI parsing, resource ownership, and execution-error translation."""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta

import typer
from pydantic import ValidationError
from typer._click.exceptions import UsageError

from src.config import settings
from src.core.constants import ConfigKeys
from src.core.provider_failure_kind import ProviderFailureKind
from src.core.telemetry.quality import record_cli_quality
from src.data.base_client import DataFetchError
from src.data.cached_client import CachedHistoricalDataClient
from src.data.financial.cache import ResolvedInputSeriesCacheProtocol
from src.data.financial.facts import FinancialProviderError
from src.data.instrument_profile_cache import CachedInstrumentProfileResolver
from src.data.quality import HistoricalQualityPolicy
from src.data.repositories import (
    SQLiteDatabase,
    SQLiteInstrumentProfileRepository,
    SQLiteMarketDataRepository,
    SQLiteResolvedInputCache,
)
from src.data.repositories.readiness import ensure_database_ready
from src.data.yfinance import YFinanceClient
from src.data.yfinance.client import YFINANCE_HISTORICAL_INTERVAL, YFINANCE_PRICE_ADJUSTMENT
from src.reporting.documents.failure import PROVIDER_FAILURE_CODES, FailureReasonCode
from src.reporting.failure_classification import classify_failure, failure_envelope
from src.reporting.presentation import PresentationMode, failure_document
from src.workspace.selection_base import FrozenSelection

logger = logging.getLogger(__name__)

_DIRECT_CODES = frozenset(
    {
        FailureReasonCode.EXECUTION_ERROR,
        FailureReasonCode.HISTORICAL_QUALITY,
        FailureReasonCode.PROVIDER_ERROR,
        *PROVIDER_FAILURE_CODES,
        FailureReasonCode.CONFIGURATION_ERROR,
        FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS,
        FailureReasonCode.INVALID_INPUT,
        FailureReasonCode.INVALID_PARAMETER,
    }
)

# One sentence per kind of provider failure, then one for a failure the adapter did not classify. Each names the
# provider (when known) and the ticker, says what was observed, and offers no remedy.
_PROVIDER_FAILURE_SENTENCES = {
    ProviderFailureKind.UNREACHABLE: "Unable to analyze {subject}: {provider} did not serve the request.",
    ProviderFailureKind.UNEXPECTED_RESPONSE: (
        "Unable to analyze {subject}: {provider} answered in a form the application does not read."
    ),
    ProviderFailureKind.NO_DATA: "Unable to analyze {subject}: {provider} returned no data for it.",
}
_UNCLASSIFIED_PROVIDER_FAILURE_SENTENCE = (
    "Unable to analyze {subject}: a data provider failed; the failure was not classified."
)


def provider_failure_sentence(error: DataFetchError | FinancialProviderError, ticker: str | None) -> str:
    """Return the sentence for a provider failure, from its kind, the provider that failed and the ticker."""
    subject = ticker or "the requested instrument"
    if error.kind is None:
        return _UNCLASSIFIED_PROVIDER_FAILURE_SENTENCE.format(subject=subject)
    return _PROVIDER_FAILURE_SENTENCES[error.kind].format(subject=subject, provider=error.provider_id)


# Failures whose own message was written to be shown: the database and quality sentences, and the
# command's own parameter guidance. No other exception's text is shown by default.
_SHOWN_AS_RAISED = frozenset(
    {
        FailureReasonCode.HISTORICAL_QUALITY,
        FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS,
        FailureReasonCode.INVALID_PARAMETER,
    }
)


@contextmanager
def _production_historical_client(
    provider: YFinanceClient, *, use_cache: bool, clock: Callable[[], datetime]
) -> Iterator[CachedHistoricalDataClient]:
    """Borrow the Yahoo client and own historical storage for one analysis.

    Daily adjusted request identity matches the provider's download configuration.
    Reuse age comes from settings. Readiness is checked and storage initialized before
    fetching only when ``use_cache`` is True; the per-call ``use_cache`` gate on the
    yielded client's own methods is what actually skips reads/writes.
    """
    database = SQLiteDatabase(settings)
    try:
        if use_cache:
            ensure_database_ready(database)
        seconds = settings.historical_cache_ttl_seconds
        yield CachedHistoricalDataClient(
            provider,
            SQLiteMarketDataRepository(database),
            request_variant=f"{YFINANCE_HISTORICAL_INTERVAL}:{YFINANCE_PRICE_ADJUSTMENT}",
            ttl=None if seconds is None else timedelta(seconds=seconds),
            clock=clock,
            quality_policy=HistoricalQualityPolicy(expected_adjustment=YFINANCE_PRICE_ADJUSTMENT),
        )
    finally:
        database.close()


@contextmanager
def _production_financial_cache(
    *, use_cache: bool, clock: Callable[[], datetime]
) -> Iterator[ResolvedInputSeriesCacheProtocol]:
    """Own one invocation's durable cache; schema upgrades remain explicit unless caching is disabled.

    Financial facts use configured residence age (unlimited by default) and
    temporal quality checks. Readiness is checked only when ``use_cache`` is True; the
    resolver's own per-call ``use_cache`` gate is what actually skips reads/writes, so
    disabling caching still never touches storage.
    """
    database = SQLiteDatabase(settings)
    try:
        if use_cache:
            ensure_database_ready(database)
        seconds = settings.financial_cache_ttl_seconds
        yield SQLiteResolvedInputCache(
            database, ttl=None if seconds is None else timedelta(seconds=seconds), clock=clock
        )
    finally:
        database.close()


def _production_instrument_profile_cache(
    database: SQLiteDatabase, *, clock: Callable[[], datetime]
) -> CachedInstrumentProfileResolver:
    """Build the durable instrument-profile cache over an already-open database.

    Unlike the historical/financial cache helpers above, this does not own or
    close ``database``: every caller already manages that lifecycle for its
    own reason (Analysis Run persistence, watchlist storage), and durable
    profiles are database-free lookups when the P2-Profiles contract calls
    for staying live-only (no database is opened here or by any caller solely
    to obtain one of these).
    """
    seconds = settings.instrument_profile_ttl_seconds
    return CachedInstrumentProfileResolver(
        SQLiteInstrumentProfileRepository(database),
        ttl=None if seconds is None else timedelta(seconds=seconds),
        clock=clock,
    )


def _presentation_mode(*, details: bool, diagnostics: bool, json_output: bool) -> PresentationMode:
    """Resolve the mutually exclusive progressive-disclosure flags."""
    selected_count = sum((details, diagnostics, json_output))
    if selected_count > 1:
        raise typer.BadParameter("Choose only one of --details, --diagnostics, or --json.")
    if json_output:
        return PresentationMode.JSON
    if diagnostics:
        return PresentationMode.DIAGNOSTICS
    if details:
        return PresentationMode.DETAILS
    return PresentationMode.CONCISE


def _resolve_ticker(positional: str | None, option: str | None, *, required: bool, command: str) -> str | None:
    """Resolve positional ticker with a transitional --ticker compatibility alias."""
    if positional is not None and option is not None and positional.strip().upper() != option.strip().upper():
        raise typer.BadParameter("Positional TICKER and --ticker refer to different symbols.")
    selected = positional if positional is not None else option
    if selected is None:
        if required:
            raise typer.BadParameter(f"TICKER is required. Use 'ian {command} TICKER'.")
        return None
    normalized = selected.strip().upper()
    if not normalized:
        raise typer.BadParameter("Ticker must be a non-empty symbol.")
    return normalized


def _default_ticker() -> str:
    """Return the configured default ticker used when a command is given none."""
    return str(settings.get_analysis_settings()[ConfigKeys.DEFAULT_SECTION][ConfigKeys.TICKER])


def _default_history_start_date() -> str:
    """Return the configured start date for historical price series."""
    return str(settings.get_analysis_settings()[ConfigKeys.DEFAULT_SECTION][ConfigKeys.START_DATE])


def _canonical_provider_id(value: str | None) -> str | None:
    """Normalize an optional provider identifier."""
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        raise typer.BadParameter("--data-provider must be non-empty when supplied.")
    return normalized


def _parse_as_of(value: str | None) -> datetime | None:
    """Parse a CLI as-of boundary without silently assuming a timestamp timezone."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise typer.BadParameter("--as-of must be non-empty when supplied.")

    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            return datetime.combine(parsed_date, time.max, tzinfo=UTC)

        normalized = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp.") from exc

    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise typer.BadParameter("Timestamp --as-of values must include an explicit timezone offset.")
    return parsed


def _selection_identity(selection_type: type[FrozenSelection] | None) -> tuple[str | None, str | None]:
    """Return the fixed analysis and method identifiers a selection class declares, or ``None`` for both."""
    if selection_type is None:
        return None, None
    fields = selection_type.model_fields
    return str(fields["analysis_id"].default), str(fields["method_id"].default)


@contextmanager
def execution_errors(  # noqa: PLR0912, PLR0913
    *,
    unexpected: Callable[[Exception], str],
    invalid: Callable[[ValueError], str] | None = None,
    invalid_detail: bool = False,
    mode: PresentationMode | None = None,
    selection_type: type[FrozenSelection] | None = None,
    ticker: str | None = None,
) -> Iterator[None]:
    """Translate execution failures while preserving deliberate CLI exits.

    The code and status of a failure come from :func:`classify_failure`, shared with the workspace
    commands. A provider failure's sentence comes from :func:`provider_failure_sentence`; the callbacks
    only choose the sentence shown: ``invalid`` for configuration guidance and, when ``invalid_detail`` is true
    or no ``mode`` is given, for a plain ``ValueError``. A plain ``ValueError`` otherwise reports the generic
    sentence, so exception text from provider data is not exposed. A failure whose callback is absent is reported
    as an unexpected one, exactly as before. ``selection_type`` is the command's own selection class,
    whose fixed ``analysis_id`` and ``method_id`` name the analysis in the failure document.
    """
    try:
        with record_cli_quality():
            yield
    except (typer.Exit, UsageError):
        raise
    except Exception as exc:
        analysis, method = _selection_identity(selection_type)
        code = classify_failure(exc).reason_code
        if code not in _DIRECT_CODES and not code.value.startswith("database_"):
            # A workspace code (for example a stored-run error raised while saving a run) is reported
            # by the direct commands as it always was: a plain invalid input, or an unexpected failure.
            code = FailureReasonCode.INVALID_INPUT if isinstance(exc, ValueError) else FailureReasonCode.EXECUTION_ERROR
        if code is FailureReasonCode.INVALID_INPUT and invalid is None:
            code = FailureReasonCode.EXECUTION_ERROR
        if code.value.startswith("database_") or code in _SHOWN_AS_RAISED:
            message = str(exc)
        elif isinstance(exc, DataFetchError | FinancialProviderError):
            message = provider_failure_sentence(exc, ticker)
        elif code is FailureReasonCode.CONFIGURATION_ERROR:
            message = invalid(exc) if invalid is not None and isinstance(exc, ValueError) else str(exc)
        elif code is FailureReasonCode.INVALID_INPUT and invalid is not None and isinstance(exc, ValueError):
            message = invalid(exc) if mode is None or invalid_detail else "Invalid analysis inputs or provider data."
        else:
            code = FailureReasonCode.EXECUTION_ERROR
            message = unexpected(exc)
            logger.exception("Unexpected failure reported to the user as: %s", message)
        envelope = failure_envelope(code, message, cause=exc, analysis=analysis, method=method, ticker=ticker)
        if mode is PresentationMode.JSON:
            typer.echo(failure_document(envelope))
        else:
            typer.echo(message, err=True)
            if mode is PresentationMode.DIAGNOSTICS:
                for diagnostic in envelope.diagnostics:
                    typer.echo(f"{diagnostic.rule}: {diagnostic.reason}", err=True)
        raise typer.Exit(code=1) from exc


@contextmanager
def config_usage_errors() -> Iterator[None]:
    """Expose concise option names without dumping configuration input values."""
    try:
        yield
    except ValidationError as exc:
        error = exc.errors(include_input=False, include_url=False)[0]
        location = error["loc"]
        names = {
            "security_provider_id": "--data-provider",
            "eps_basis": "--eps-basis",
            "eps_override": "--eps",
            "bvps_override": "--bvps",
            "quote_override": "--current-price",
            "expected_growth": "--expected-growth",
            "aaa_yield_override": "--aaa-yield",
            "as_of": "--as-of",
        }
        if location:
            option = names.get(str(location[0]), "Graham options")
            message = f"Invalid {option}: {error['msg']}"
        else:
            message = error["msg"].removeprefix("Value error, ")
            for field, option in names.items():
                message = message.replace(field, option)
        raise typer.BadParameter(message) from exc
