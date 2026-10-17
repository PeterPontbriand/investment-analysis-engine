"""Shared CLI parsing, resource ownership, and execution-error translation."""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import ClassVar, NoReturn

import typer
from pydantic import ValidationError

from investment_analysis_engine.analysis.selection_base import FrozenSelection
from investment_analysis_engine.cli_provider_check import (
    ProviderCheckChoice,
    echo_provider_check,
    provider_check_findings,
)
from investment_analysis_engine.config import settings
from investment_analysis_engine.core.failure_classification import classify_failure
from investment_analysis_engine.core.failure_codes import PROVIDER_FAILURE_CODES, FailureReasonCode
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.cached_client import CachedHistoricalDataClient
from investment_analysis_engine.data.financial.cache import ResolvedInputSeriesCacheProtocol
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.instrument_profile_cache import CachedInstrumentProfileResolver
from investment_analysis_engine.data.quality import HistoricalQualityPolicy
from investment_analysis_engine.data.repositories.instrument_profiles import SQLiteInstrumentProfileRepository
from investment_analysis_engine.data.repositories.market_data import SQLiteMarketDataRepository
from investment_analysis_engine.data.repositories.readiness import ensure_database_ready
from investment_analysis_engine.data.repositories.resolved_input_cache import SQLiteResolvedInputCache
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.yfinance.client import (
    YFINANCE_HISTORICAL_INTERVAL,
    YFINANCE_PRICE_ADJUSTMENT,
    YFinanceClient,
)
from investment_analysis_engine.reporting.documents.failure import FailureEnvelope
from investment_analysis_engine.reporting.failure_envelope import failure_envelope
from investment_analysis_engine.reporting.presentation import PresentationMode, failure_document
from investment_analysis_engine.telemetry.quality import record_cli_quality
from investment_analysis_engine.workspace.capture import ExecutionCapture

logger = logging.getLogger(__name__)
# Without a configured handler (``--no-logging``) Python's last-resort handler would write the logged failure and its
# traceback to standard error; the null handler keeps standard error to the failure message alone.
logger.addHandler(logging.NullHandler())

# One sentence per kind of provider failure, then one for a failure the adapter did not classify. Each names the
# provider (when known) and the ticker, says what was observed, and offers no remedy.
_PROVIDER_FAILURE_SENTENCES = {
    ProviderFailureKind.UNREACHABLE: "Unable to analyze {subject}: {provider} did not serve the request.",
    ProviderFailureKind.RATE_LIMITED: "Unable to analyze {subject}: {provider} is limiting requests.",
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


# Failures whose own message was written to be shown: the quality, parameter and configuration messages, and the
# database messages (every code that starts with ``database_``). No other exception's text is shown.
_SHOWN_AS_RAISED = frozenset(
    {
        FailureReasonCode.HISTORICAL_QUALITY,
        FailureReasonCode.NO_ELIGIBLE_OBSERVATIONS,
        FailureReasonCode.INVALID_PARAMETER,
        FailureReasonCode.CONFIGURATION_ERROR,
    }
)
_PROVIDER_CODES = frozenset({FailureReasonCode.PROVIDER_ERROR, *PROVIDER_FAILURE_CODES})


class InternalDefectError(Exception):
    """A failure only a defect can cause, such as a stored selection that no longer converts to a configuration."""

    reason_code: ClassVar[FailureReasonCode] = FailureReasonCode.EXECUTION_ERROR


def stored_configuration[ConfigT](convert: Callable[[], ConfigT]) -> ConfigT:
    """Return the configuration ``convert`` builds from a stored selection; a validation failure is a defect."""
    try:
        return convert()
    except ValidationError as exc:
        raise InternalDefectError("A stored selection no longer converts to a configuration.") from exc


def require_job_ticker(ticker: str) -> str:
    """Return ``ticker`` unchanged; a blank ticker in a refresh job is a defect."""
    if not ticker.strip():
        raise InternalDefectError("A refresh job has a blank ticker.")
    return ticker


@dataclass(frozen=True)
class FailureDescription:
    """The code of a failure and the one message shown for it."""

    code: FailureReasonCode
    message: str


def describe_failure(exception: BaseException, ticker: str | None, *, saving: bool) -> FailureDescription:
    """Return the code and the message of a failure; the direct commands and refresh share this rule.

    The failure code chooses the message and no message names a strategy. A provider code gives
    :func:`provider_failure_sentence`; the codes in ``_SHOWN_AS_RAISED`` and every ``database_*`` code show the
    exception's own text; ``invalid_input`` and ``execution_error`` each have one fixed message. A failure while the
    analysis result is being saved (``saving``) has the save message and the code it classifies to. Any other code
    is reported as ``execution_error``. Wherever a fixed message replaces the exception's text, the exception is
    logged with its traceback.

    Args:
        exception: The failure.
        ticker: The ticker the job or command resolved, or ``None`` before one was.
        saving: Whether the analysis had finished and its result was being saved.

    Returns:
        The code and the message.
    """
    code = classify_failure(exception).reason_code
    subject = ticker or "the requested instrument"
    if saving:
        message = f"{ticker or 'The requested instrument'} was analyzed, but the result could not be saved."
    elif code in _PROVIDER_CODES and isinstance(exception, DataFetchError | FinancialProviderError):
        message = provider_failure_sentence(exception, ticker)
    elif code.value.startswith("database_") or code in _SHOWN_AS_RAISED:
        return FailureDescription(code=code, message=str(exception))
    elif code is FailureReasonCode.INVALID_INPUT:
        message = f"Unable to analyze {subject}: invalid analysis inputs or provider data."
    else:
        code = FailureReasonCode.EXECUTION_ERROR
        message = f"Unable to analyze {subject}: the analysis failed unexpectedly."
    logger.error("Failure reported to the user as: %s", message, exc_info=exception)
    return FailureDescription(code=code, message=message)


class SaveStage:
    """Tells ``saving_failures`` whether the analysis has finished, so a later failure is a failure while saving."""

    def __init__(self, *, analyzed: bool = False) -> None:
        """Start before the analysis, or after it when ``analyzed`` is true."""
        self.analyzed = analyzed

    def after_analysis[RawCaptureT](
        self, normalize: Callable[[RawCaptureT], ExecutionCapture]
    ) -> Callable[[RawCaptureT], ExecutionCapture]:
        """Wrap ``normalize`` so that the stage is marked analyzed once it has returned."""

        def marked(raw: RawCaptureT) -> ExecutionCapture:
            capture = normalize(raw)
            self.analyzed = True
            return capture

        return marked


class SavingFailureError(Exception):
    """An exception raised after the analysis finished, while its result was saved; ``cause`` is the original."""

    def __init__(self, cause: Exception) -> None:
        """Keep the original exception."""
        super().__init__(str(cause))
        self.cause = cause


@contextmanager
def saving_failures(stage: SaveStage) -> Iterator[None]:
    """Re-raise an exception from the block as :class:`SavingFailureError` once ``stage`` says the analysis finished.

    ``typer.Exit`` and an exception raised before the analysis finished pass through unchanged.
    """
    try:
        yield
    except typer.Exit:
        raise
    except Exception as exc:
        if stage.analyzed:
            raise SavingFailureError(exc) from exc
        raise


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
    selected = tuple(
        name
        for name, given in (("--details", details), ("--diagnostics", diagnostics), ("--json", json_output))
        if given
    )
    if len(selected) > 1:
        raise InvalidParameterError("Choose only one of --details, --diagnostics, or --json.", parameters=selected)
    if json_output:
        return PresentationMode.JSON
    if diagnostics:
        return PresentationMode.DIAGNOSTICS
    if details:
        return PresentationMode.DETAILS
    return PresentationMode.CONCISE


def _resolve_ticker(positional: str | None, option: str | None, *, command: str) -> str:
    """Resolve positional ticker with a transitional --ticker compatibility alias."""
    if positional is not None and option is not None and positional.strip().upper() != option.strip().upper():
        raise InvalidParameterError(
            "Positional TICKER and --ticker refer to different symbols.", parameters=("TICKER", "--ticker")
        )
    selected = positional if positional is not None else option
    if selected is None:
        raise InvalidParameterError(f"TICKER is required. Use 'ian {command} TICKER'.", parameters=("TICKER",))
    normalized = selected.strip().upper()
    if not normalized:
        name = "TICKER" if positional is not None else "--ticker"
        raise InvalidParameterError(f"{name} must be a non-empty symbol.", parameters=(name,))
    return normalized


def _production_database() -> SQLiteDatabase:
    """Return the application database, which the caller opens, checks for readiness and closes."""
    return SQLiteDatabase(settings)


def _canonical_provider_id(value: str | None) -> str | None:
    """Normalize an optional provider identifier."""
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        raise InvalidParameterError("--data-provider must be non-empty when supplied.", parameters=("--data-provider",))
    return normalized


def _parse_as_of(value: str | None) -> datetime | None:
    """Parse a CLI as-of boundary without silently assuming a timestamp timezone."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise InvalidParameterError("--as-of must be non-empty when supplied.", parameters=("--as-of",))

    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            return datetime.combine(parsed_date, time.max, tzinfo=UTC)

        normalized = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InvalidParameterError(
            "--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp.", parameters=("--as-of",)
        ) from exc

    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise InvalidParameterError(
            "Timestamp --as-of values must include an explicit timezone offset.", parameters=("--as-of",)
        )
    return parsed


def _selection_identity(selection_type: type[FrozenSelection] | None) -> tuple[str | None, str | None]:
    """Return the fixed analysis and method identifiers a selection class declares, or ``None`` for both."""
    if selection_type is None:
        return None, None
    fields = selection_type.model_fields
    return str(fields["analysis_id"].default), str(fields["method_id"].default)


@dataclass
class FailureScope:
    """What a failure document needs that a command only learns while it runs.

    A command sets ``ticker`` and ``mode`` as soon as it has resolved them, so a failure raised by an earlier check
    is reported with whatever is known by then. ``mode`` starts as ``JSON`` when ``--json`` was given, so a check that
    fails before the presentation mode is resolved (the exclusive output flags among them) still writes the envelope.
    """

    ticker: str | None
    mode: PresentationMode | None


def report_failure(envelope: FailureEnvelope, *, json_output: bool) -> NoReturn:
    """Write one failure envelope to standard output, or its sentence to standard error, and exit 1."""
    if json_output:
        typer.echo(failure_document(envelope))
    else:
        typer.echo(envelope.reason, err=True)
    raise typer.Exit(code=1)


@contextmanager
def parameter_failures(*, json_output: bool) -> Iterator[None]:
    """Report an ``InvalidParameterError`` raised inside the block as an ``invalid_parameter`` failure.

    This is the path for every command that has no analysis to name: the sentence on standard error, or with
    ``json_output`` the failure envelope on standard output, and exit 1. A command with no ``--json`` passes
    ``False``. ``typer.Exit`` and every other exception pass through.
    """
    try:
        yield
    except InvalidParameterError as exc:
        envelope = failure_envelope(classify_failure(exc).reason_code, str(exc), cause=exc)
        report_failure(envelope, json_output=json_output)


@contextmanager
def execution_errors(
    *,
    json_output: bool = False,
    mode: PresentationMode | None = None,
    selection_type: type[FrozenSelection] | None = None,
    ticker: str | None = None,
    provider_check: ProviderCheckChoice | None = None,
) -> Iterator[FailureScope]:
    """Translate execution failures while preserving deliberate CLI exits.

    The code and message of a failure come from :func:`describe_failure`, shared with refresh. A
    :class:`SavingFailureError` is described as a failure while saving, from its original exception. ``selection_type``
    is the command's own selection class, whose fixed ``analysis_id`` and ``method_id`` name the analysis in the
    failure document. When a raised provider failure names its provider and ``provider_check`` is given, the check
    runs once: its lines are written to standard error immediately before the failure text in every mode but
    ``--json``, and in ``--json`` mode the failure envelope carries its findings as ``provider_check`` and nothing
    extra is printed.

    A command enters the block before it checks its own arguments and sets ``scope.ticker`` and ``scope.mode`` on
    the yielded :class:`FailureScope` as it resolves them, so a rejected argument is reported through the same
    path as any other failure. ``json_output`` is the raw ``--json`` flag and fixes the scope's initial mode.
    """
    initial_mode = mode if mode is not None else (PresentationMode.JSON if json_output else None)
    scope = FailureScope(ticker=ticker, mode=initial_mode)
    try:
        with record_cli_quality():
            yield scope
    except typer.Exit:
        raise
    except Exception as exc:
        analysis, method = _selection_identity(selection_type)
        cause = exc.cause if isinstance(exc, SavingFailureError) else exc
        description = describe_failure(cause, scope.ticker, saving=isinstance(exc, SavingFailureError))
        envelope = failure_envelope(
            description.code, description.message, cause=cause, analysis=analysis, method=method, ticker=scope.ticker
        )
        findings = provider_check_findings((envelope.provider_failure,), provider_check)
        if scope.mode is PresentationMode.JSON:
            typer.echo(failure_document(envelope.with_provider_check(findings.element())))
        else:
            echo_provider_check(findings, err=True)
            typer.echo(description.message, err=True)
            if scope.mode is PresentationMode.DIAGNOSTICS:
                for diagnostic in envelope.diagnostics:
                    typer.echo(f"{diagnostic.rule}: {diagnostic.reason}", err=True)
        raise typer.Exit(code=1) from cause


@contextmanager
def config_usage_errors() -> Iterator[None]:
    """Report a rejected Graham option as an ``invalid_parameter`` failure without dumping input values.

    A field-level error names the option its field maps to. A model-level error has its field names replaced by
    option names, and the options it names are the offending parameters. An unmapped field is a programming error:
    the lookup is strict and fails loudly instead of inventing an option name.
    """
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
        text = error["msg"].removeprefix("Value error, ")
        if location:
            option = names[str(location[0])]
            raise InvalidParameterError(f"Invalid {option}: {text}", parameters=(option,)) from exc
        parameters = tuple(option for field, option in names.items() if field in text)
        if not parameters:
            raise
        message = text
        for field, option in names.items():
            message = message.replace(field, option)
        raise InvalidParameterError(message, parameters=parameters) from exc
