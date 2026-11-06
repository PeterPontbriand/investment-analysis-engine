"""Shared CLI parsing, resource ownership, and execution-error translation."""

import json
import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any, NoReturn

import typer
from pydantic import BaseModel

from investment_analysis_engine.analysis.selection_base import FrozenSelection
from investment_analysis_engine.application.analysis import AnalysisOutcome, analyze, exit_code_of
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.failures import SavingFailureError
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.selections import build_selection
from investment_analysis_engine.application.watchlists import add_watchlist_entries, alias_for_method_id
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
from investment_analysis_engine.workspace.runs import Watchlist, WatchlistEntry
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection, SelectionMember
from investment_analysis_engine.workspace.watchlists import StoredSelectionError, WatchlistName
from investment_analysis_engine.workspace_documents.watchlist import build_watchlist_document

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


def cache_enabled(no_cache: bool) -> bool:
    """Translate ``--no-cache`` into the selection's ``use_cache`` field."""
    return not no_cache


def parse_as_of(value: str | None) -> date | datetime | None:
    """Parse the syntax of a CLI as-of boundary into a date or a timestamp.

    A ``YYYY-MM-DD`` value is returned as a date and a timestamp as it was written. The end-of-day rule for a date and
    the requirement of a timezone offset on a timestamp belong to the selection's builder, which every caller uses.

    Raises:
        InvalidParameterError: If ``value`` is empty or is neither a date nor an ISO-8601 timestamp.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise InvalidParameterError("--as-of must be non-empty when supplied.", parameters=("--as-of",))

    try:
        if len(text) == 10:
            return date.fromisoformat(text)

        normalized = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InvalidParameterError(
            "--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp.", parameters=("--as-of",)
        ) from exc


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
) -> Iterator[FailureScope]:
    """Translate execution failures while preserving deliberate CLI exits.

    The code and message of a failure come from :func:`describe_failure`, shared with refresh. A
    :class:`SavingFailureError` is described as a failure while saving, from its original exception. ``selection_type``
    is the command's own selection class, whose fixed ``analysis_id`` and ``method_id`` name the analysis in the
    failure document. A provider failure leaves the direct-analysis operation as a stored run, never as an exception, so
    the provider check is the operation's and this block runs none.

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
        if scope.mode is PresentationMode.JSON:
            typer.echo(failure_document_json(envelope))
        else:
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

AS_OF_OPTION = Annotated[str | None, typer.Option("--as-of", help=AS_OF_HELP)]
"""The ``--as-of`` option every direct command declares with this text; the default is ``None``."""

SAVE_RUN_OPTION = Annotated[bool, typer.Option("--save-run", help="Persist this attempt as a durable Analysis Run")]
"""The ``--save-run`` option every direct command declares with this text; the default is ``False``."""

NO_PROVIDER_CHECK_OPTION = Annotated[
    bool, typer.Option("--no-provider-check", help="Do not send a test request to a provider after it fails")
]
"""The ``--no-provider-check`` option every direct command declares with this text; the default is ``False``."""


@dataclass(frozen=True)
class SelectionOption:
    """One selection field and the command-line option that sets it.

    A strategy's table of these rows is the only place the command line and the selection model meet: the direct
    command and the ``add-selection`` command both build their selection through it, and the validation messages,
    which name model fields, are spelled with its options.

    Attributes:
        parameter: The name of the command parameter that holds the option's value.
        field: The selection field the option sets, written ``outer.inner`` for a field of a nested model.
        option: The option's primary long spelling, which names the field in a message.
        convert: Translates the option's value into the field's value when they differ in more than their name,
            such as ``--no-cache`` into ``use_cache``. It may reject a value that has no spelling as a field value
            and keeps the message the command line has always given for it. ``None`` means the value is the field's.
    """

    parameter: str
    field: str
    option: str
    convert: Callable[[Any], object] | None = None


def selection_from_options(
    method_id: str, table: Sequence[SelectionOption], values: Mapping[str, object]
) -> SelectionMember:
    """Build a strategy's selection from the command's option values through the strategy's option table.

    An option whose value is ``None`` was not given and leaves its field to the configured default or the model's.

    Args:
        method_id: The strategy's canonical method identifier.
        table: The strategy's option table.
        values: Each command parameter's value, by parameter name.

    Raises:
        InvalidParameterError: If a converter rejects a value or the selection breaks a rule; the message names the
            options.
    """
    fields: dict[str, object] = {}
    for row in table:
        value = values[row.parameter]
        if value is None:
            continue
        target = fields
        *parents, leaf = row.field.split(".")
        for parent in parents:
            nested = target.setdefault(parent, {})
            assert isinstance(nested, dict)  # a parent field holds a mapping, set only here
            target = nested
        target[leaf] = row.convert(value) if row.convert is not None else value
    try:
        return build_selection(application_context(), method_id, fields)
    except ActionParameterError as error:
        raise error.named({row.field: row.option for row in table}) from None


@contextmanager
def workspace_failures(command: str, *, json_output: bool = False) -> Iterator[None]:
    """Report a failure raised inside the block as a sanitized message and exit 1.

    ``command`` is the command as the user types it after ``ian``. A readiness error, or an exception raised inside
    the block that declares its own ``reason_code`` (a rejected parameter, an unreadable stored selection, a missing
    watchlist), keeps its own message; any other exception is an ``execution_error`` with one fixed message naming
    the command, and its detail goes to the log with its traceback, so no library text reaches the user.
    ``json_output`` selects the failure envelope on standard output instead of text on standard error.
    """
    try:
        yield
    except (typer.Exit, typer.Abort):
        raise
    except Exception as exc:
        if isinstance(getattr(exc, "reason_code", None), FailureReasonCode):
            fail_with(exc, json_output=json_output)
        logger.exception("Unexpected failure in 'ian %s'.", command)
        fail(FailureReasonCode.EXECUTION_ERROR, f"{command} failed unexpectedly.", json_output=json_output)


def fail(reason_code: FailureReasonCode, message: str, *, json_output: bool = False) -> NoReturn:
    """Report a sanitized lookup or storage failure under ``reason_code`` and exit 1.

    With ``json_output`` the failure envelope is written to standard output and nothing to standard
    error, as the direct commands do; otherwise the message goes to standard error.
    """
    report_failure(failure_envelope(reason_code, message), json_output=json_output)


def operator_message(exception: Exception) -> str:
    """Return the exception's own message, with the command that removes an unreadable watchlist entry.

    The stored-selection error names the entry and its state; the command that removes it is the CLI's to offer.
    """
    message = str(exception)
    if isinstance(exception, StoredSelectionError) and exception.watchlist_name is not None:
        message += f' Remove it with: ian watchlist remove-entry "{exception.watchlist_name}" {exception.entry_number}'
    return message


def fail_with(exception: Exception, *, json_output: bool = False) -> NoReturn:
    """Report a classified failure with the exception's own sanitized message and exit 1."""
    classification = classify_failure(exception)
    envelope = failure_envelope(classification.reason_code, operator_message(exception), cause=exception)
    report_failure(envelope, json_output=json_output)


@contextmanager
def watchlist_action(command: str, parameters: Mapping[str, str], *, json_output: bool = False) -> Iterator[None]:
    """Report a failure of a watchlist action as :func:`workspace_failures` does, in the command's own spelling.

    ``parameters`` maps each parameter name the action rejects under to the argument or option of ``command``,
    so an action's parameter error is reported as the command has always spelled it.
    """
    with workspace_failures(command, json_output=json_output):
        try:
            yield
        except ActionParameterError as exc:
            raise exc.named(parameters) from None


def selection_detail_text(selection: AnalysisSelection) -> str:
    """Render a selection's distinguishing fields, excluding its own identifiers."""
    payload = selection.model_dump(mode="json")
    payload.pop("method_id", None)
    payload.pop("analysis_id", None)
    payload.pop("config_schema_version", None)
    return ", ".join(f"{key}={value}" for key, value in sorted(payload.items()))


def selection_summary(selection: AnalysisSelection) -> str:
    """Render one selection's method alias and distinguishing fields, compactly."""
    detail = selection_detail_text(selection)
    alias = alias_for_method_id(selection.method_id)
    return f"{alias}: {detail}" if detail else alias


def entry_line(entry: WatchlistEntry, *, group_by: str) -> str:
    """Render one entry's line, showing whichever axis isn't already the group heading."""
    if group_by == "method":
        detail = selection_detail_text(entry.selection)
        return f"{entry.ticker}: {detail}" if detail else entry.ticker
    return selection_summary(entry.selection)


def watchlist_text(watchlist: Watchlist, *, group_by: str = "ticker") -> str:
    """Render a watchlist's entries, numbered from 1 and grouped by ticker or method."""
    lines = [
        f"Watchlist: {watchlist.display_name}",
        f"ID: {watchlist.watchlist_id}",
        f"Entries ({len(watchlist.entries)}):",
    ]
    if not watchlist.entries:
        lines.append("  (none)")
        return "\n".join(lines)

    key_of: Callable[[WatchlistEntry], str] = (
        (lambda entry: alias_for_method_id(entry.selection.method_id))
        if group_by == "method"
        else (lambda entry: entry.ticker)
    )
    groups: dict[str, list[tuple[int, WatchlistEntry]]] = {}
    for index, entry in enumerate(watchlist.entries, start=1):
        groups.setdefault(key_of(entry), []).append((index, entry))
    for key, members in groups.items():
        lines.append(f"  {key}:")
        lines.extend(f"    [{index}] {entry_line(entry, group_by=group_by)}" for index, entry in members)
    return "\n".join(lines)


def document_json(document: BaseModel) -> str:
    """Serialize a typed document as the one line of JSON a command writes."""
    return json.dumps(document.model_dump(mode="json"), ensure_ascii=False, allow_nan=False)


def watchlist_json(watchlist: Watchlist) -> str:
    """Emit the complete watchlist document."""
    return document_json(build_watchlist_document(watchlist))


_ADD_SELECTION_PARAMETERS = {"tickers": "TICKER"}


def add_selection_entries(name: str, tickers: Sequence[str], selection: SelectionMember, *, json_output: bool) -> None:
    """Add one entry per ticker for ``selection`` to the named watchlist and print the watchlist.

    Used by every strategy's ``add-selection`` command once it has built its selection. The watchlist is printed as
    text, or with ``json_output`` as the watchlist document.
    """
    entries = [(ticker, selection) for ticker in tickers]
    with watchlist_action("watchlist add-selection", _ADD_SELECTION_PARAMETERS, json_output=json_output):
        watchlist = add_watchlist_entries(application_context(), WatchlistName(name), entries)
    typer.echo(watchlist_json(watchlist) if json_output else watchlist_text(watchlist))
