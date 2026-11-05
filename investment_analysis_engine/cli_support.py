"""Shared CLI parsing, resource ownership, and execution-error translation."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import NoReturn

import typer
from pydantic import ValidationError

from investment_analysis_engine.analysis.selection_base import FrozenSelection
from investment_analysis_engine.application.analysis import AnalysisOutcome, analyze, exit_code_of
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.failures import SavingFailureError
from investment_analysis_engine.application.provider_check import ProviderCheckChoice, provider_check_findings
from investment_analysis_engine.application.providers import build_provider_probe
from investment_analysis_engine.cli_provider_check import echo_provider_check
from investment_analysis_engine.config import settings
from investment_analysis_engine.core.failure_classification import classify_failure
from investment_analysis_engine.core.failure_codes import PROVIDER_FAILURE_CODES, FailureReasonCode
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.reporting.documents.failure import FailureEnvelope
from investment_analysis_engine.reporting.documents.strategy_document import strategy_document_json
from investment_analysis_engine.reporting.failure_envelope import failure_envelope
from investment_analysis_engine.reporting.presentation import PresentationMode, failure_document_json
from investment_analysis_engine.telemetry.quality import record_cli_quality
from investment_analysis_engine.telemetry.run_context import RunContext, get_current_run_context
from investment_analysis_engine.workspace.strategy_types import SelectionMember

logger = logging.getLogger(__name__)
# Without a configured handler (``--no-logging``) Python's last-resort handler would write the logged failure and its
# traceback to standard error; the null handler keeps standard error to the failure message alone.
logger.addHandler(logging.NullHandler())

# One message per kind of provider failure, then one for a failure the adapter did not classify. Each names the
# provider (when known) and the ticker, says what was observed, and offers no remedy.
_PROVIDER_FAILURE_MESSAGES = {
    ProviderFailureKind.UNREACHABLE: "Unable to analyze {subject}: {provider} did not serve the request.",
    ProviderFailureKind.RATE_LIMITED: "Unable to analyze {subject}: {provider} is limiting requests.",
    ProviderFailureKind.UNEXPECTED_RESPONSE: (
        "Unable to analyze {subject}: {provider} answered in a form the application does not read."
    ),
    ProviderFailureKind.NO_DATA: "Unable to analyze {subject}: {provider} returned no data for it.",
}
_UNCLASSIFIED_PROVIDER_FAILURE_MESSAGE = (
    "Unable to analyze {subject}: a data provider failed; the failure was not classified."
)


def provider_failure_message(error: DataFetchError | FinancialProviderError, ticker: str | None) -> str:
    """Return the message for a provider failure, from its kind, the provider that failed and the ticker."""
    subject = ticker or "the requested instrument"
    if error.kind is None:
        return _UNCLASSIFIED_PROVIDER_FAILURE_MESSAGE.format(subject=subject)
    return _PROVIDER_FAILURE_MESSAGES[error.kind].format(subject=subject, provider=error.provider_id)


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


@dataclass(frozen=True)
class FailureDescription:
    """The code of a failure and the one message shown for it."""

    code: FailureReasonCode
    message: str


def describe_failure(exception: BaseException, ticker: str | None, *, saving: bool) -> FailureDescription:
    """Return the code and the message of a failure; the direct commands and refresh share this rule.

    The failure code chooses the message and no message names a strategy. A provider code gives
    :func:`provider_failure_message`; the codes in ``_SHOWN_AS_RAISED`` and every ``database_*`` code show the
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
        message = provider_failure_message(exception, ticker)
    elif code.value.startswith("database_") or code in _SHOWN_AS_RAISED:
        return FailureDescription(code=code, message=str(exception))
    elif code is FailureReasonCode.INVALID_INPUT:
        message = f"Unable to analyze {subject}: invalid analysis inputs or provider data."
    else:
        code = FailureReasonCode.EXECUTION_ERROR
        message = f"Unable to analyze {subject}: the analysis failed unexpectedly."
    logger.error("Failure reported to the user as: %s", message, exc_info=exception)
    return FailureDescription(code=code, message=message)


def get_cli_run_context() -> RunContext:
    """Return the explicit execution identity for the current CLI invocation."""
    context = get_current_run_context()
    if context is None:
        raise RuntimeError("CLI RunContext has not been initialized.")
    return context


def presentation_mode(*, details: bool, diagnostics: bool, json_output: bool) -> PresentationMode:
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


def resolve_ticker(positional: str | None, option: str | None, *, command: str) -> str:
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


def production_database() -> SQLiteDatabase:
    """Return the application database, which the caller opens, checks for readiness and closes."""
    return SQLiteDatabase(settings)


def application_context() -> ApplicationContext:
    """Return the application context for a command: this module's settings."""
    return ApplicationContext(settings=settings)


def parse_as_of(value: str | None) -> datetime | None:
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
    """Write one failure envelope to standard output, or its message to standard error, and exit 1."""
    if json_output:
        typer.echo(failure_document_json(envelope))
    else:
        typer.echo(envelope.reason, err=True)
    raise typer.Exit(code=1)


@contextmanager
def parameter_failures(*, json_output: bool) -> Iterator[None]:
    """Report an ``InvalidParameterError`` raised inside the block as an ``invalid_parameter`` failure.

    This is the path for every command that has no analysis to name: the message on standard error, or with
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
    provider_check: bool | None = None,
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
        choice = (
            None
            if provider_check is None
            else ProviderCheckChoice(build_provider_probe(application_context()), requested=provider_check)
        )
        findings = provider_check_findings((envelope.provider_failure,), choice)
        if scope.mode is PresentationMode.JSON:
            typer.echo(failure_document_json(envelope.with_provider_check(findings.element())))
        else:
            echo_provider_check(findings, err=True)
            typer.echo(description.message, err=True)
            if scope.mode is PresentationMode.DIAGNOSTICS:
                for diagnostic in envelope.diagnostics:
                    typer.echo(f"{diagnostic.rule}: {diagnostic.reason}", err=True)
        raise typer.Exit(code=1) from cause


def resolve_command_target(  # noqa: PLR0913
    scope: FailureScope,
    positional: str | None,
    option: str | None,
    *,
    command: str,
    details: bool,
    diagnostics: bool,
    json_output: bool,
) -> tuple[str, PresentationMode]:
    """Resolve a direct command's ticker and presentation mode, recording each on ``scope`` as soon as it is known.

    The ticker is resolved and recorded first, so a rejected output flag is still reported with the ticker.

    Args:
        scope: The failure scope the command entered before checking its arguments.
        positional: The positional ticker, or ``None``.
        option: The legacy ``--ticker`` value, or ``None`` for a command that has no such option.
        command: The command's name, as its "ticker is required" message spells it.
        details: Whether ``--details`` was given.
        diagnostics: Whether ``--diagnostics`` was given.
        json_output: Whether ``--json`` was given.

    Returns:
        The normalized ticker and the presentation mode.
    """
    target_ticker = resolve_ticker(positional, option, command=command)
    scope.ticker = target_ticker
    mode = presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    scope.mode = mode
    return target_ticker, mode


def analysis_output(outcome: AnalysisOutcome, mode: PresentationMode) -> tuple[str, int]:
    """Return the text a direct command writes for a finished analysis and its exit code.

    ``--json`` writes the outcome's document, which carries the provider-check element; every text mode writes what the
    outcome renders, which after a failure starts with the provider-check lines. The exit code is the one
    :func:`exit_code_of` gives for the run's outcome.
    """
    output = strategy_document_json(outcome.document) if mode is PresentationMode.JSON else outcome.render_text(mode)
    return output, exit_code_of(outcome.outcome)


def analyze_for_command(  # noqa: PLR0913
    ticker: str,
    selection: SelectionMember,
    *,
    save_run: bool,
    provider_check: bool,
) -> AnalysisOutcome:
    """Run the analysis operation for a direct command and report the saved run's ID on standard error.

    The ID is written before the result, as it always has been, and only when the run was saved.
    """
    outcome = analyze(application_context(), ticker, selection, save=save_run, provider_check=provider_check)
    if outcome.analysis_run_id is not None:
        typer.echo(f"Saved Analysis Run: {outcome.analysis_run_id}", err=True)
    return outcome


def emit_output(output: str, exit_code: int, mode: PresentationMode) -> None:
    """Write a direct command's output and exit with ``exit_code`` when it is not zero.

    A failure is written to standard error in the concise and details modes only, so ``--json`` and ``--diagnostics``
    keep their document on standard output.
    """
    typer.echo(output, err=exit_code != 0 and mode in (PresentationMode.CONCISE, PresentationMode.DETAILS))
    if exit_code:
        raise typer.Exit(code=exit_code)


AS_OF_HELP = "Point-in-time boundary as YYYY-MM-DD or timezone-aware ISO-8601 timestamp"
"""The help text of every ``--as-of`` option, which every selection carries."""

AS_OF_OPTION = typer.Option(None, "--as-of", help=AS_OF_HELP)
"""The ``--as-of`` option every direct command declares with this text."""

SAVE_RUN_OPTION = typer.Option(False, "--save-run", help="Persist this attempt as a durable Analysis Run")
"""The ``--save-run`` option every direct command declares with this text."""

NO_PROVIDER_CHECK_OPTION = typer.Option(
    False, "--no-provider-check", help="Do not send a test request to a provider after it fails"
)
"""The ``--no-provider-check`` option every direct command declares with this text."""


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
