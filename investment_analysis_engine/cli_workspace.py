"""Watchlist, Analysis Run browsing, and refresh CLI: F1/F2/G3 of the local research workspace.

This module owns explicit Typer sub-apps and the bare ``refresh`` command; it
performs no storage or provider work at import time. Every command opens its
own short-lived, readiness-checked :class:`SQLiteDatabase`, borrows it for
one repository call, and closes it before returning — mirroring the existing
``production_historical_client``/``production_financial_cache`` pattern in
``investment_analysis_engine.application.providers``. Direct-command saving (``--save-run``) lives in
``investment_analysis_engine.application.analysis``; this module's own provider/analyzer composition exists solely
to dispatch one refresh job per stored selection.
"""

import ctypes
import logging
import signal
import sys
import threading
from typing import Annotated
from uuid import UUID

import typer

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.refresh import refresh_watchlist
from investment_analysis_engine.application.runs import (
    RunQueryNames,
    build_run_query,
    compare_refresh_runs,
    list_runs,
    parse_refresh_id,
    replay_run_document,
    replay_run_text,
)
from investment_analysis_engine.application.watchlists import (
    alias_for_method_id,
    create_watchlist,
    delete_watchlist,
    get_watchlist_by_name,
    get_watchlist_summary,
    list_watchlists,
    remove_watchlist_entry,
    remove_watchlist_method,
    remove_watchlist_tickers,
    rename_watchlist,
)
from investment_analysis_engine.cli_strategy_wiring import add_selection_commands
from investment_analysis_engine.cli_support import (
    document_json,
    fail_with,
    parameter_failures,
    presentation_mode,
    watchlist_action,
    watchlist_json,
    watchlist_text,
    workspace_failures,
)
from investment_analysis_engine.config import settings
from investment_analysis_engine.config.paths import is_windows
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.core.strategy_errors import require
from investment_analysis_engine.reporting.documents.strategy_document import strategy_document_json
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategy_wiring import BY_ALIAS
from investment_analysis_engine.workspace.refresh import DEFAULT_WORKERS
from investment_analysis_engine.workspace.repositories.watchlists import DeletedWatchlist, RemovedEntries
from investment_analysis_engine.workspace.runs import (
    AnalysisRunSummary,
    WatchlistSummary,
)
from investment_analysis_engine.workspace.watchlists import (
    WatchlistId,
    WatchlistName,
    WatchlistNotFoundError,
    WatchlistRef,
)
from investment_analysis_engine.workspace_documents.runs import build_runs_list_document
from investment_analysis_engine.workspace_documents.runs_compare import render_runs_compare_text
from investment_analysis_engine.workspace_documents.watchlist import (
    WatchlistDeleteDocument,
    build_watchlist_document,
    build_watchlist_list_document,
)

logger = logging.getLogger(__name__)

watchlist_app = typer.Typer(help="Manage named watchlists of tickers and their analysis selections.")
runs_app = typer.Typer(help="Browse persisted Analysis Run history.")
add_selection_app = typer.Typer(help="Add entries for one method to an existing watchlist, one per ticker.")
add_selection_commands(add_selection_app)
watchlist_app.add_typer(add_selection_app, name="add-selection")


def _alias_choices() -> str:
    """Return the CLI tier's alias vocabulary as help text: ``a, b, or c``."""
    aliases = list(BY_ALIAS)
    return f"{', '.join(aliases[:-1])}, or {aliases[-1]}"


_ANALYSIS_CHOICES = _alias_choices()

_RUN_QUERY_NAMES = RunQueryNames(
    ticker="--ticker",
    method="--analysis",
    status="--status",
    refresh_id="--refresh-id",
    limit="--limit",
    offset="--offset",
)
"""The runs-list options, spelled as the command declares them."""


_CREATE_PARAMETERS = {"name": "NAME"}
_REFRESH_PARAMETERS = {"workers": "--workers"}
_REMOVE_ENTRY_PARAMETERS = {"entry_number": "INDEX"}
_REMOVE_TICKER_PARAMETERS = {"tickers": "TICKER"}
_RENAME_PARAMETERS = {"new_name": "NEW_NAME"}


def _method_id_for_alias(alias: str) -> str:
    """Return the canonical method identifier of a validated CLI alias."""
    return require(BY_ALIAS, alias, what="alias").method_id


def _summary_line(summary: WatchlistSummary) -> str:
    plural = "y" if summary.entry_count == 1 else "ies"
    return f"{summary.display_name} ({summary.watchlist_id}): {summary.entry_count} entr{plural}"


def _parse_analysis(value: str) -> str:
    """Normalize and validate a watchlist ``--analysis`` alias."""
    normalized = value.strip().lower()
    if normalized not in BY_ALIAS:
        allowed = ", ".join(BY_ALIAS)
        raise InvalidParameterError(f"--analysis must be one of: {allowed}.", parameters=("--analysis",))
    return normalized


@watchlist_app.command("create")
def watchlist_create(
    name: Annotated[str, typer.Argument(help="Display name for the new watchlist.")],
    *,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the created watchlist document.")] = False,
) -> None:
    """Create an empty watchlist.

    Add entries to it with 'ian watchlist add-selection METHOD NAME TICKER...'.
    """
    with watchlist_action("watchlist create", _CREATE_PARAMETERS, json_output=json_output):
        watchlist = create_watchlist(ApplicationContext(settings=settings), name)
    typer.echo(watchlist_json(watchlist) if json_output else watchlist_text(watchlist))


def _plural_entries(count: int) -> str:
    """Return ``"1 entry"`` or ``"N entries"``."""
    return "1 entry" if count == 1 else f"{count} entries"


def _removal_confirmation(count: int, name: str, subject: str | None) -> str:
    """Describe a committed removal; ``subject`` is the ticker(s) or method it was for, if any."""
    if count == 0:
        return f"No entries for {subject} in watchlist {name!r}."
    scope = "" if subject is None else f" for {subject}"
    return f"Removed {_plural_entries(count)}{scope} from watchlist {name!r}."


def _report_removal(removed: RemovedEntries, confirmation: str, *, json_output: bool) -> None:
    """Report a removal that has already committed: the confirmation, then the watchlist read back with it.

    The confirmation goes to standard output, or to standard error with ``json_output`` so that standard output
    holds only the document. If another entry cannot be read, the removal stands: the error naming the next
    unreadable entry and the command that removes it follows, and the command exits 1.
    """
    typer.echo(confirmation, err=json_output)
    if removed.watchlist is None:
        assert removed.unreadable is not None  # exactly one of watchlist and unreadable is set
        fail_with(removed.unreadable, json_output=json_output)
    typer.echo(watchlist_json(removed.watchlist) if json_output else watchlist_text(removed.watchlist))


@watchlist_app.command("remove-entry")
def watchlist_remove_entry(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    index: Annotated[int, typer.Argument(help="1-based entry number, as shown by 'watchlist show'.")],
    *,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the updated watchlist document.")] = False,
) -> None:
    """Remove exactly one entry by its displayed 1-based index."""
    with watchlist_action("watchlist remove-entry", _REMOVE_ENTRY_PARAMETERS, json_output=json_output):
        removed = remove_watchlist_entry(ApplicationContext(settings=settings), WatchlistName(name), index)
    _report_removal(removed, _removal_confirmation(removed.removed, name, None), json_output=json_output)


@watchlist_app.command("remove-ticker")
def watchlist_remove_ticker(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to remove every entry for, across every method.")],
    *,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the updated watchlist document.")] = False,
) -> None:
    """Remove every entry for the given ticker(s), across every method (bulk, idempotent)."""
    with watchlist_action("watchlist remove-ticker", _REMOVE_TICKER_PARAMETERS, json_output=json_output):
        removed = remove_watchlist_tickers(ApplicationContext(settings=settings), WatchlistName(name), tickers)
    _report_removal(removed, _removal_confirmation(removed.removed, name, ", ".join(tickers)), json_output=json_output)


@watchlist_app.command("remove-method")
def watchlist_remove_method(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    *,
    analysis: Annotated[
        str, typer.Option("--analysis", "-a", help="Method to remove every entry for, across every ticker.")
    ],
    json_output: Annotated[bool, typer.Option("--json", help="Emit the updated watchlist document.")] = False,
) -> None:
    """Remove every entry for the given method, across every ticker (bulk, idempotent)."""
    with parameter_failures(json_output=json_output):
        method = _parse_analysis(analysis)
    with workspace_failures("watchlist remove-method", json_output=json_output):
        removed = remove_watchlist_method(
            ApplicationContext(settings=settings), WatchlistName(name), _method_id_for_alias(method)
        )
    _report_removal(removed, _removal_confirmation(removed.removed, name, method), json_output=json_output)


def _windows_console_attached() -> bool:  # pragma: no cover - needs a real Windows console handle
    """Report whether standard input is a real Windows console, not merely a character device."""
    kernel32 = getattr(ctypes, "WinDLL")("kernel32")  # noqa: B009 - typeshed defines WinDLL on Windows only
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    kernel32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    mode = ctypes.c_uint32()
    return bool(kernel32.GetConsoleMode(kernel32.GetStdHandle(-10), ctypes.byref(mode)))


def _stdin_is_interactive() -> bool:
    """Report whether standard input is an interactive terminal; the one seam tests control.

    Windows reports the NUL device, which is what a script's redirected-from-nothing standard input
    is, as a terminal, so there ``isatty()`` alone would let a script reach a prompt nobody can answer.
    """
    if not sys.stdin.isatty():
        return False
    return _windows_console_attached() if is_windows() else True


@watchlist_app.command("delete")
def watchlist_delete(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    *,
    yes: Annotated[bool, typer.Option("--yes", help="Delete without asking for confirmation.")] = False,
    missing_ok: Annotated[
        bool, typer.Option("--missing-ok", help="Exit 0 instead of 1 when no such watchlist exists.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit one JSON document describing the outcome.")] = False,
) -> None:
    """Delete a watchlist and its entries. Saved Analysis Runs are kept.

    Asks for confirmation on an interactive terminal; without one, --yes is required.
    """
    with parameter_failures(json_output=json_output):
        if not yes and not _stdin_is_interactive():
            raise InvalidParameterError("--yes is required when input is not interactive.", parameters=("--yes",))
    deleted: DeletedWatchlist | None = None
    context = ApplicationContext(settings=settings)
    with workspace_failures("watchlist delete", json_output=json_output):
        try:
            ref: WatchlistRef = WatchlistName(name)
            if not yes:
                summary = get_watchlist_summary(context, ref)
                question = (
                    f"Delete watchlist {summary.display_name!r} (ID {summary.watchlist_id}, "
                    f"{_plural_entries(summary.entry_count)})? Saved Analysis Runs are kept."
                )
                if not typer.confirm(question):
                    typer.echo("Nothing was deleted.")
                    raise typer.Exit(code=1)
                # Delete the watchlist that was asked about: a rename since the summary cannot redirect the delete.
                ref = WatchlistId(summary.watchlist_id)
            deleted = delete_watchlist(context, ref)
        except WatchlistNotFoundError as exc:
            if not missing_ok:
                fail_with(exc, json_output=json_output)
    if deleted is None:
        if json_output:
            typer.echo(document_json(WatchlistDeleteDocument(requested_name=name, deleted=False, watchlist=None)))
        else:
            typer.echo(f"No watchlist named {name!r} exists. Nothing was deleted.")
        return
    confirmation = (
        f"Deleted watchlist {deleted.display_name!r} (ID {deleted.watchlist_id}, "
        f"{_plural_entries(deleted.entry_count)}). Saved Analysis Runs are kept."
    )
    if not json_output:
        typer.echo(confirmation)
        return
    if deleted.watchlist is None:
        typer.echo(confirmation, err=True)
        assert deleted.unreadable is not None  # exactly one of watchlist and unreadable is set
        fail_with(deleted.unreadable, json_output=json_output)
    document = WatchlistDeleteDocument(
        requested_name=name, deleted=True, watchlist=build_watchlist_document(deleted.watchlist)
    )
    typer.echo(document_json(document))


@watchlist_app.command("rename")
def watchlist_rename(
    name: Annotated[str, typer.Argument(help="Current watchlist name.")],
    new_name: Annotated[str, typer.Argument(help="New display name.")],
    *,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the renamed watchlist document.")] = False,
) -> None:
    """Rename a watchlist. Saved Analysis Runs keep the name it had when they ran."""
    with watchlist_action("watchlist rename", _RENAME_PARAMETERS, json_output=json_output):
        renamed = rename_watchlist(ApplicationContext(settings=settings), WatchlistName(name), new_name)
    confirmation = f"Renamed watchlist {name!r} to {new_name.strip()!r}."
    if not json_output:
        typer.echo(confirmation)
    if renamed.watchlist is None:
        if json_output:
            typer.echo(confirmation, err=True)
        assert renamed.unreadable is not None  # exactly one of watchlist and unreadable is set
        fail_with(renamed.unreadable, json_output=json_output)
    typer.echo(watchlist_json(renamed.watchlist) if json_output else watchlist_text(renamed.watchlist))


@watchlist_app.command("list")
def watchlist_list(
    *,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit one JSON object holding the watchlist summaries.")
    ] = False,
) -> None:
    """List every watchlist with its entry count."""
    with workspace_failures("watchlist list", json_output=json_output):
        summaries = list_watchlists(ApplicationContext(settings=settings))
    if json_output:
        typer.echo(document_json(build_watchlist_list_document(summaries)))
        return
    if not summaries:
        typer.echo("No watchlists exist yet.")
        return
    for summary in summaries:
        typer.echo(_summary_line(summary))


@watchlist_app.command("show")
def watchlist_show(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    *,
    group_by: Annotated[
        str, typer.Option("--group-by", help="Group text output by 'ticker' (default) or 'method'.")
    ] = "ticker",
    json_output: Annotated[bool, typer.Option("--json", help="Emit the complete watchlist document.")] = False,
) -> None:
    """Show one watchlist's entries, numbered from 1 (see 'remove-entry')."""
    normalized_group_by = group_by.strip().lower()
    with parameter_failures(json_output=json_output):
        if normalized_group_by not in ("ticker", "method"):
            raise InvalidParameterError("--group-by must be 'ticker' or 'method'.", parameters=("--group-by",))
    with workspace_failures("watchlist show", json_output=json_output):
        watchlist = get_watchlist_by_name(ApplicationContext(settings=settings), name)
    typer.echo(watchlist_json(watchlist) if json_output else watchlist_text(watchlist, group_by=normalized_group_by))


@runs_app.command("list")
def runs_list(  # noqa: PLR0913
    *,
    ticker: Annotated[str | None, typer.Option("--ticker", help="Filter by exact normalized ticker.")] = None,
    analysis: Annotated[
        str | None,
        typer.Option("--analysis", "-a", help=f"Filter by method: {_ANALYSIS_CHOICES}."),
    ] = None,
    status: Annotated[str | None, typer.Option("--status", help="Filter by outcome.")] = None,
    refresh_id: Annotated[
        str | None, typer.Option("--refresh-id", help="Filter by refresh batch ID (the full UUID shown by 'refresh').")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum rows (1-100).")] = 20,
    offset: Annotated[int, typer.Option("--offset", help="Rows to skip.")] = 0,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit one JSON object holding a page of run summaries.")
    ] = False,
) -> None:
    """List Analysis Run summaries, most recently completed first."""
    with parameter_failures(json_output=json_output):
        query = build_run_query(
            names=_RUN_QUERY_NAMES,
            resolve_method=lambda alias: _method_id_for_alias(_parse_analysis(alias)),
            ticker=ticker,
            method=analysis,
            status=status,
            refresh_id=refresh_id,
            limit=limit,
            offset=offset,
        )
    with workspace_failures("runs list", json_output=json_output):
        page = list_runs(ApplicationContext(settings=settings), query)
    summaries = page.summaries
    if json_output:
        typer.echo(document_json(build_runs_list_document(summaries, has_more=page.has_more)))
        return
    if not summaries:
        typer.echo("No matching runs.")
        return
    for item in summaries:
        typer.echo(_run_summary_line(item))


@runs_app.command("show")
def runs_show(
    run_id: Annotated[str, typer.Argument(help="Analysis Run ID (the full UUID shown by 'runs list').")],
    details: Annotated[bool, typer.Option("--details", help="Show provenance and derivations.")] = False,
    diagnostics: Annotated[bool, typer.Option("--diagnostics", help="Show resolution/execution trace.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the versioned run projection.")] = False,
) -> None:
    """Replay one stored run using only its own captured evidence."""
    with parameter_failures(json_output=json_output):
        mode = presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
        parsed_id = _parse_run_id(run_id, field="RUN_ID")
    context = ApplicationContext(settings=settings)
    with workspace_failures("runs show", json_output=json_output):
        if mode is PresentationMode.JSON:
            rendered = strategy_document_json(replay_run_document(context, parsed_id))
        else:
            rendered = replay_run_text(context, parsed_id, mode)
    typer.echo(rendered)


@runs_app.command("compare")
def runs_compare(
    refresh_id: Annotated[str, typer.Argument(help="Refresh ID (the full UUID shown by 'refresh').")],
    json_output: Annotated[bool, typer.Option("--json", help="Emit the complete table as one document.")] = False,
) -> None:
    """Show the runs of one refresh side by side: one row per ticker, one column group per strategy."""
    with parameter_failures(json_output=json_output):
        parsed_id = parse_refresh_id(refresh_id, name="REFRESH_ID")
    with workspace_failures("runs compare", json_output=json_output):
        document = compare_refresh_runs(ApplicationContext(settings=settings), parsed_id)
    typer.echo(document_json(document) if json_output else render_runs_compare_text(document))


def _parse_run_id(value: str, *, field: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise InvalidParameterError(
            f"{field} {value!r} is not a valid Analysis Run ID. Use the full ID exactly as shown "
            "by 'runs list' or 'refresh' — not a shortened or partial value.",
            parameters=(field,),
        ) from exc


def _run_summary_line(summary: AnalysisRunSummary) -> str:
    return (
        f"{summary.analysis_run_id}  {summary.ticker:<10} {alias_for_method_id(summary.method_id):<24} "
        f"{summary.status.value:<14} {summary.completed_at.isoformat()}"
    )


def refresh(  # noqa: PLR0913
    name: Annotated[str, typer.Argument(help="Watchlist name to refresh.")],
    *,
    workers: Annotated[
        int, typer.Option("--workers", help="Concurrent job count, 1-4; defaults to 2.")
    ] = DEFAULT_WORKERS,
    no_save: Annotated[
        bool,
        typer.Option("--no-save", help="Preview current numbers across the watchlist without saving any Analysis Run."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit one final JSON summary document.")] = False,
    no_provider_check: Annotated[
        bool,
        typer.Option(
            "--no-provider-check", help="Do not send a test request to a provider whose failure the summary reports"
        ),
    ] = False,
) -> None:
    """Execute every entry in a watchlist and, by default, persist each result.

    Nothing is printed until the refresh completes or is interrupted: no
    per-job progress chatter reaches stdout, only the final summary. A
    Ctrl+C during the refresh stops admitting new jobs, lets any job already
    running finish and persist normally, and exits 130 without a fabricated
    row for a job that never started. With --no-save every entry still runs,
    but nothing is written to storage; each result is shown but has no
    Analysis Run ID to browse or replay afterward.

    When a job failed on a provider, one test request per implicated
    provider runs after the batch ends. Its finding is printed before the
    summary, or carried in the summary document as provider_check with
    --json. --no-provider-check turns it off.
    """
    cancellation = threading.Event()
    previous_handler = signal.getsignal(signal.SIGINT)

    def _handle_sigint(signum: int, frame: object) -> None:
        del signum, frame
        cancellation.set()

    signal.signal(signal.SIGINT, _handle_sigint)
    try:
        with watchlist_action("refresh", _REFRESH_PARAMETERS, json_output=json_output):
            outcome = refresh_watchlist(
                ApplicationContext(settings=settings),
                WatchlistName(name),
                workers=workers,
                save=not no_save,
                provider_check=not no_provider_check,
                cancellation=cancellation,
            )
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    typer.echo(document_json(outcome.document) if json_output else outcome.render_text())

    if cancellation.is_set():
        raise typer.Exit(code=130)
    if outcome.failed:
        raise typer.Exit(code=1)


def register(app: typer.Typer) -> None:
    """Register the watchlist and runs sub-apps, and the refresh command, on the root Typer app."""
    app.add_typer(watchlist_app, name="watchlist")
    app.add_typer(runs_app, name="runs")
    app.command("refresh")(refresh)


__all__ = ["register", "runs_app", "watchlist_app"]
