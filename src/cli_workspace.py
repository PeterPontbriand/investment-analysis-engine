"""Watchlist, Analysis Run browsing, and refresh CLI: F1/F2/G3 of the local research workspace.

This module owns explicit Typer sub-apps and the bare ``refresh`` command; it
performs no storage or provider work at import time. Every command opens its
own short-lived, readiness-checked :class:`SQLiteDatabase`, borrows it for
one repository call, and closes it before returning — mirroring the existing
``_production_historical_client``/``_production_financial_cache`` pattern in
``src.cli_support``. Direct-command saving (``--save-run``) lives in
``src.cli_run_support``; this module's own provider/analyzer composition exists solely
to dispatch one refresh job per stored selection.
"""

import ctypes
import json
import signal
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Annotated, NoReturn
from uuid import UUID

import typer
from pydantic import BaseModel

from src.cli_strategy_wiring import CLI_BUILDERS, build_selection_for, refresh_executor_for
from src.cli_support import _production_instrument_profile_cache
from src.cli_watchlist_flags import WatchlistFlags
from src.config import settings
from src.core.clock import utc_now
from src.core.strategy_errors import find, require
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.readiness import DatabaseReadinessError, ensure_database_ready
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.repositories.watchlists import (
    DeletedWatchlist,
    SQLiteWatchlistRepository,
    WatchlistConflictError,
    WatchlistEntryNotFoundError,
)
from src.reporting.analysis_runs import ReplayOptions, UnsupportedProjectionError, project_run
from src.reporting.documents.failure import FailureEnvelope, FailureReasonCode
from src.reporting.documents.refresh import RefreshResultDocument, RefreshSummaryDocument
from src.reporting.documents.runs import RunsListDocument, RunSummaryDocument
from src.reporting.documents.watchlist import WatchlistDeleteDocument, WatchlistDocument, WatchlistEntryDocument
from src.reporting.failure_classification import InvalidParameterError, classify_failure, failure_envelope
from src.reporting.presentation import PresentationMode, failure_document
from src.strategies.momentum.analyzer import MomentumConfig
from src.strategy_wiring import BY_ALIAS, BY_METHOD_ID, EVIDENCE_BY_KEY, RUN_SPECS_BY_KEY
from src.utils.paths import is_windows
from src.workspace.capture import ExecutionCapture
from src.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError
from src.workspace.models import RunOutcome
from src.workspace.refresh import (
    EmptyRefreshTargetError,
    RefreshJobResult,
    RefreshPolicy,
    RefreshSummary,
    refresh_watchlist,
)
from src.workspace.runs import AnalysisRunSummary, RunQuery, Watchlist, WatchlistEntry, WatchlistSummary
from src.workspace.strategy_types import AnalysisSelection
from src.workspace.watchlists import StoredSelectionError, WatchlistNotFoundError, WatchlistSpec, normalize_ticker

watchlist_app = typer.Typer(help="Manage named watchlists of tickers and their analysis selections.")
runs_app = typer.Typer(help="Browse persisted Analysis Run history.")

_MOMENTUM_CLI_DEFAULTS = MomentumConfig()


def _alias_choices() -> str:
    """Return the CLI tier's alias vocabulary as help text: ``a, b, or c``."""
    aliases = list(CLI_BUILDERS)
    return f"{', '.join(aliases[:-1])}, or {aliases[-1]}"


_ANALYSIS_CHOICES = _alias_choices()


@contextmanager
def _workspace_database(*, json_output: bool = False) -> Iterator[SQLiteDatabase]:
    """Own one invocation's readiness-checked database connection.

    A readiness failure is reported as a sanitized message and exit 1 here,
    at the one place every command shares, rather than repeated per command.
    ``json_output`` selects the failure envelope on standard output instead of text on standard error.
    """
    database = SQLiteDatabase(settings)
    try:
        try:
            ensure_database_ready(database)
        except DatabaseReadinessError as exc:
            _fail_with(exc, json_output=json_output)
        try:
            yield database
        except StoredSelectionError as exc:
            _fail_with(exc, json_output=json_output)
    finally:
        database.close()


def _fail(reason_code: FailureReasonCode, message: str, *, json_output: bool = False) -> NoReturn:
    """Report a sanitized lookup or storage failure under ``reason_code`` and exit 1.

    With ``json_output`` the failure envelope is written to standard output and nothing to standard
    error, as the direct commands do; otherwise the sentence goes to standard error.
    """
    _report(failure_envelope(reason_code, message), json_output=json_output)


def _fail_with(exception: Exception, *, json_output: bool = False) -> NoReturn:
    """Report a classified failure with the exception's own sanitized message and exit 1."""
    classification = classify_failure(exception)
    _report(failure_envelope(classification.reason_code, str(exception), cause=exception), json_output=json_output)


def _report(envelope: FailureEnvelope, *, json_output: bool) -> NoReturn:
    """Write one failure envelope or its sentence and exit 1."""
    if json_output:
        typer.echo(failure_document(envelope))
    else:
        typer.echo(envelope.reason, err=True)
    raise typer.Exit(code=1)


def _alias_for_method_id(method_id: str) -> str:
    """Return the CLI alias of a declared method; an undeclared one is a programming error, not a fallback."""
    return require(BY_METHOD_ID, method_id, what="method id").alias


def _method_id_for_alias(alias: str) -> str:
    """Return the canonical method identifier of a validated CLI alias."""
    return require(BY_ALIAS, alias, what="alias").method_id


def _stored_method_alias(method_id: str) -> str | None:
    """Return the alias of a stored method identifier, or ``None`` if this version declares no such method."""
    descriptor = find(BY_METHOD_ID, method_id)
    return None if descriptor is None else descriptor.alias


def _watchlist_repository(database: SQLiteDatabase) -> SQLiteWatchlistRepository:
    """Compose the watchlist repository with the declared strategies' alias vocabulary."""
    return SQLiteWatchlistRepository(database, alias_for=_stored_method_alias)


def _selection_detail_text(selection: AnalysisSelection) -> str:
    """Render a selection's distinguishing fields, excluding its own identifiers."""
    payload = selection.model_dump(mode="json")
    payload.pop("method_id", None)
    payload.pop("analysis_id", None)
    payload.pop("config_schema_version", None)
    return ", ".join(f"{key}={value}" for key, value in sorted(payload.items()))


def _selection_summary(selection: AnalysisSelection) -> str:
    """Render one selection's method alias and distinguishing fields, compactly."""
    detail = _selection_detail_text(selection)
    alias = _alias_for_method_id(selection.method_id)
    return f"{alias}: {detail}" if detail else alias


def _entry_line(entry: WatchlistEntry, *, group_by: str) -> str:
    """Render one entry's line, showing whichever axis isn't already the group heading."""
    if group_by == "method":
        detail = _selection_detail_text(entry.selection)
        return f"{entry.ticker}: {detail}" if detail else entry.ticker
    return _selection_summary(entry.selection)


def _watchlist_text(watchlist: Watchlist, *, group_by: str = "ticker") -> str:
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
        (lambda entry: _alias_for_method_id(entry.selection.method_id))
        if group_by == "method"
        else (lambda entry: entry.ticker)
    )
    groups: dict[str, list[tuple[int, WatchlistEntry]]] = {}
    for index, entry in enumerate(watchlist.entries, start=1):
        groups.setdefault(key_of(entry), []).append((index, entry))
    for key, members in groups.items():
        lines.append(f"  {key}:")
        lines.extend(f"    [{index}] {_entry_line(entry, group_by=group_by)}" for index, entry in members)
    return "\n".join(lines)


def _document_json(document: BaseModel) -> str:
    """Serialize a typed document as the one line of JSON a command writes."""
    return json.dumps(document.model_dump(mode="json"), ensure_ascii=False, allow_nan=False)


def _watchlist_document(watchlist: Watchlist) -> WatchlistDocument:
    """Build the watchlist document: the flat, ordered entry list, each carrying the 1-based index a user sees."""
    return WatchlistDocument(
        watchlist_id=watchlist.watchlist_id,
        display_name=watchlist.display_name,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        entries=tuple(
            WatchlistEntryDocument(index=index, ticker=entry.ticker, selection=entry.selection)
            for index, entry in enumerate(watchlist.entries, start=1)
        ),
    )


def _watchlist_json(watchlist: Watchlist) -> str:
    """Emit the complete watchlist document."""
    return _document_json(_watchlist_document(watchlist))


def _summary_line(summary: WatchlistSummary) -> str:
    plural = "y" if summary.entry_count == 1 else "ies"
    return f"{summary.display_name} ({summary.watchlist_id}): {summary.entry_count} entr{plural}"


def _parse_analysis(value: str) -> str:
    """Normalize and validate a watchlist ``--analysis`` alias."""
    normalized = value.strip().lower()
    if normalized not in CLI_BUILDERS:
        allowed = ", ".join(CLI_BUILDERS)
        raise typer.BadParameter(f"--analysis must be one of: {allowed}.")
    return normalized


def _build_selection(  # noqa: PLR0913
    method: str,
    *,
    short_window: int,
    long_window: int,
    rsi_period: int,
    as_of: str | None,
    data_provider: str | None,
    no_cache: bool,
    eps: float | None,
    eps_basis: str | None,
    bvps: float | None,
    current_price: float | None,
    expected_growth: float | None,
    aaa_yield: float | None,
    growth_years: int | None,
    forward_policy: str,
    classification_basis: str,
    currency: str,
) -> AnalysisSelection:
    """Build one validated selection from watchlist CLI flags with the selection builder of ``method``.

    The builder belongs to the strategy and mirrors its direct command's own flags and validation exactly
    (Amendment A1, §12's "Creation"/"Editing" sections), so a watchlist entry behaves identically to running
    that method directly. Only the flags relevant to ``method`` are consulted; the rest are ignored.
    """
    flags = WatchlistFlags(
        short_window=short_window,
        long_window=long_window,
        rsi_period=rsi_period,
        as_of=as_of,
        data_provider=data_provider,
        no_cache=no_cache,
        eps=eps,
        eps_basis=eps_basis,
        bvps=bvps,
        current_price=current_price,
        expected_growth=expected_growth,
        aaa_yield=aaa_yield,
        growth_years=growth_years,
        forward_policy=forward_policy,
        classification_basis=classification_basis,
        currency=currency,
    )
    try:
        return build_selection_for(method, flags)
    except InvalidParameterError as exc:
        _fail_with(exc)


@watchlist_app.command("create")
def watchlist_create(  # noqa: PLR0913
    name: Annotated[str, typer.Argument(help="Display name for the new watchlist.")],
    tickers: Annotated[
        list[str] | None,
        typer.Argument(help="Tickers to seed with --analysis; omit to create an empty watchlist."),
    ] = None,
    *,
    analysis: Annotated[
        str | None,
        typer.Option("--analysis", "-a", help=f"Method to seed: {_ANALYSIS_CHOICES}."),
    ] = None,
    short_window: Annotated[
        int, typer.Option("--short-window", "-s", help="Short SMA window in daily observations (momentum).")
    ] = _MOMENTUM_CLI_DEFAULTS.short_window,
    long_window: Annotated[
        int, typer.Option("--long-window", "-l", help="Long SMA window in daily observations (momentum).")
    ] = _MOMENTUM_CLI_DEFAULTS.long_window,
    rsi_period: Annotated[
        int, typer.Option("--rsi-period", help="RSI lookback period in daily observations (momentum).")
    ] = _MOMENTUM_CLI_DEFAULTS.rsi_period,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Point-in-time boundary (momentum/graham-number/graham-growth/fcf-growth)."),
    ] = None,
    data_provider: Annotated[
        str | None,
        typer.Option("--data-provider", help="Security-fact provider override (graham-number/graham-growth)."),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help=(
                "Bypass cache reads/writes: resolved inputs for graham-number/graham-growth/fcf-growth; "
                "for momentum, the historical price cache."
            ),
        ),
    ] = False,
    eps: Annotated[
        float | None, typer.Option("--eps", "-e", help="Explicit EPS override (graham-number/graham-growth).")
    ] = None,
    eps_basis: Annotated[
        str | None, typer.Option("--eps-basis", help="EPS basis override (graham-number/graham-growth).")
    ] = None,
    bvps: Annotated[
        float | None,
        typer.Option("--bvps", help="Explicit book value per common share override (graham-number only)."),
    ] = None,
    current_price: Annotated[
        float | None,
        typer.Option("--current-price", "-p", help="Explicit current-price override (graham-number/graham-growth)."),
    ] = None,
    expected_growth: Annotated[
        float | None,
        typer.Option(
            "--expected-growth",
            "--expected-growth-rate",
            "-g",
            help="Expected annual growth in percentage points (graham-growth; required).",
        ),
    ] = None,
    aaa_yield: Annotated[
        float | None,
        typer.Option(
            "--aaa-yield",
            "--current-aaa-yield",
            "-y",
            help="Current AAA corporate-bond yield in percentage points (graham-growth; required).",
        ),
    ] = None,
    growth_years: Annotated[
        int | None,
        typer.Option("--growth-years", help="Strict elapsed-year horizon 3, 4, or 5 (fcf-growth)."),
    ] = None,
    forward_policy: Annotated[
        str, typer.Option("--forward-policy", help="Forward evidence policy (fcf-growth).")
    ] = "display-only",
    classification_basis: Annotated[
        str, typer.Option("--classification-basis", help="Classification basis (fcf-growth).")
    ] = "total-fcf",
    currency: Annotated[
        str, typer.Option("--currency", help="ISO 4217 reporting currency for compatible annual facts (fcf-growth).")
    ] = "USD",
) -> None:
    """Create a watchlist, optionally seeded with one method across the given tickers.

    ``--analysis METHOD TICKER...`` seeds one entry per given ticker for that
    method in the same command — the common single-method/multiple-ticker
    case (Amendment A1, §12's "Creation"). Method-specific flags mirror the
    matching direct command's own flags exactly, including which are
    required; a method missing a required flag (for example, graham-growth
    without --expected-growth/--aaa-yield) is a usage error exactly as the
    direct command's own validation already produces. Omit --analysis to
    create an empty watchlist, exactly as before.
    """
    seed_tickers = tickers or []
    if analysis is None and seed_tickers:
        raise typer.BadParameter("--analysis is required to seed TICKER... at creation.")
    if analysis is not None and not seed_tickers:
        raise typer.BadParameter("At least one TICKER is required with --analysis.")

    entries: list[tuple[str, AnalysisSelection]] = []
    if analysis is not None:
        method = _parse_analysis(analysis)
        selection = _build_selection(
            method,
            short_window=short_window,
            long_window=long_window,
            rsi_period=rsi_period,
            as_of=as_of,
            data_provider=data_provider,
            no_cache=no_cache,
            eps=eps,
            eps_basis=eps_basis,
            bvps=bvps,
            current_price=current_price,
            expected_growth=expected_growth,
            aaa_yield=aaa_yield,
            growth_years=growth_years,
            forward_policy=forward_policy,
            classification_basis=classification_basis,
            currency=currency,
        )
        entries = [(ticker, selection) for ticker in seed_tickers]

    with _workspace_database() as database:
        repository = _watchlist_repository(database)
        try:
            watchlist = repository.create(WatchlistSpec(display_name=name))
        except WatchlistConflictError as exc:
            _fail_with(exc)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        if entries:
            try:
                watchlist = repository.add_entries(watchlist.display_name, entries)
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
    typer.echo(_watchlist_text(watchlist))


@watchlist_app.command("add-selection")
def watchlist_add_selection(  # noqa: PLR0913
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to add this selection for.")],
    *,
    analysis: Annotated[
        str,
        typer.Option("--analysis", "-a", help=f"Method: {_ANALYSIS_CHOICES}."),
    ],
    short_window: Annotated[
        int, typer.Option("--short-window", "-s", help="Short SMA window in daily observations (momentum).")
    ] = _MOMENTUM_CLI_DEFAULTS.short_window,
    long_window: Annotated[
        int, typer.Option("--long-window", "-l", help="Long SMA window in daily observations (momentum).")
    ] = _MOMENTUM_CLI_DEFAULTS.long_window,
    rsi_period: Annotated[
        int, typer.Option("--rsi-period", help="RSI lookback period in daily observations (momentum).")
    ] = _MOMENTUM_CLI_DEFAULTS.rsi_period,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Point-in-time boundary (momentum/graham-number/graham-growth/fcf-growth)."),
    ] = None,
    data_provider: Annotated[
        str | None,
        typer.Option("--data-provider", help="Security-fact provider override (graham-number/graham-growth)."),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help=(
                "Bypass cache reads/writes: resolved inputs for graham-number/graham-growth/fcf-growth; "
                "for momentum, the historical price cache."
            ),
        ),
    ] = False,
    eps: Annotated[
        float | None, typer.Option("--eps", "-e", help="Explicit EPS override (graham-number/graham-growth).")
    ] = None,
    eps_basis: Annotated[
        str | None, typer.Option("--eps-basis", help="EPS basis override (graham-number/graham-growth).")
    ] = None,
    bvps: Annotated[
        float | None,
        typer.Option("--bvps", help="Explicit book value per common share override (graham-number only)."),
    ] = None,
    current_price: Annotated[
        float | None,
        typer.Option("--current-price", "-p", help="Explicit current-price override (graham-number/graham-growth)."),
    ] = None,
    expected_growth: Annotated[
        float | None,
        typer.Option(
            "--expected-growth",
            "--expected-growth-rate",
            "-g",
            help="Expected annual growth in percentage points (graham-growth; required).",
        ),
    ] = None,
    aaa_yield: Annotated[
        float | None,
        typer.Option(
            "--aaa-yield",
            "--current-aaa-yield",
            "-y",
            help="Current AAA corporate-bond yield in percentage points (graham-growth; required).",
        ),
    ] = None,
    growth_years: Annotated[
        int | None,
        typer.Option("--growth-years", help="Strict elapsed-year horizon 3, 4, or 5 (fcf-growth)."),
    ] = None,
    forward_policy: Annotated[
        str, typer.Option("--forward-policy", help="Forward evidence policy (fcf-growth).")
    ] = "display-only",
    classification_basis: Annotated[
        str, typer.Option("--classification-basis", help="Classification basis (fcf-growth).")
    ] = "total-fcf",
    currency: Annotated[
        str, typer.Option("--currency", help="ISO 4217 reporting currency for compatible annual facts (fcf-growth).")
    ] = "USD",
) -> None:
    """Append one entry per given ticker for one method to an existing watchlist.

    The same one-command fan-out as ``create`` (Amendment A1, §12's
    "Editing"), for adding a method to a watchlist that already exists.
    Method-specific flags mirror the matching direct command's own flags
    exactly, including which are required.
    """
    method = _parse_analysis(analysis)
    selection = _build_selection(
        method,
        short_window=short_window,
        long_window=long_window,
        rsi_period=rsi_period,
        as_of=as_of,
        data_provider=data_provider,
        no_cache=no_cache,
        eps=eps,
        eps_basis=eps_basis,
        bvps=bvps,
        current_price=current_price,
        expected_growth=expected_growth,
        aaa_yield=aaa_yield,
        growth_years=growth_years,
        forward_policy=forward_policy,
        classification_basis=classification_basis,
        currency=currency,
    )
    entries = [(ticker, selection) for ticker in tickers]
    with _workspace_database() as database:
        repository = _watchlist_repository(database)
        try:
            watchlist = repository.add_entries(name, entries)
        except WatchlistNotFoundError as exc:
            _fail_with(exc)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    typer.echo(_watchlist_text(watchlist))


def _plural_entries(count: int) -> str:
    """Return ``"1 entry"`` or ``"N entries"``."""
    return "1 entry" if count == 1 else f"{count} entries"


def _removal_confirmation(count: int, name: str, subject: str | None) -> str:
    """Describe a committed removal; ``subject`` is the ticker(s) or method it was for, if any."""
    if count == 0:
        return f"No entries for {subject} in watchlist {name!r}."
    scope = "" if subject is None else f" for {subject}"
    return f"Removed {_plural_entries(count)}{scope} from watchlist {name!r}."


def _read_back_after_removal(repository: SQLiteWatchlistRepository, name: str, confirmation: str) -> Watchlist:
    """Read a watchlist back to display it after a removal that has already committed.

    ``confirmation`` is printed first on every path. If another entry cannot be read, the
    removal stands: the error naming the next unreadable entry and the command that removes it
    follows, and the command exits 1.
    """
    typer.echo(confirmation)
    try:
        watchlist = repository.get(name)
    except StoredSelectionError as exc:
        _fail_with(exc)
    if watchlist is None:
        _fail(FailureReasonCode.WATCHLIST_NOT_FOUND, f"No watchlist named {name!r} exists.")
    return watchlist


@watchlist_app.command("remove-entry")
def watchlist_remove_entry(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    index: Annotated[int, typer.Argument(help="1-based entry number, as shown by 'watchlist show'.")],
) -> None:
    """Remove exactly one entry by its displayed 1-based index (Amendment A1, §12)."""
    if index < 1:
        raise typer.BadParameter("INDEX must be 1 or greater.")
    with _workspace_database() as database:
        repository = _watchlist_repository(database)
        try:
            removed = repository.remove_entry(name, index - 1)
        except (WatchlistNotFoundError, WatchlistEntryNotFoundError) as exc:
            _fail_with(exc)
        watchlist = _read_back_after_removal(repository, name, _removal_confirmation(removed, name, None))
    typer.echo(_watchlist_text(watchlist))


@watchlist_app.command("remove-ticker")
def watchlist_remove_ticker(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to remove every entry for, across every method.")],
) -> None:
    """Remove every entry for the given ticker(s), across every method (bulk, idempotent)."""
    with _workspace_database() as database:
        repository = _watchlist_repository(database)
        try:
            removed = repository.remove_entries_for_ticker(name, tickers)
        except WatchlistNotFoundError as exc:
            _fail_with(exc)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        watchlist = _read_back_after_removal(repository, name, _removal_confirmation(removed, name, ", ".join(tickers)))
    typer.echo(_watchlist_text(watchlist))


@watchlist_app.command("remove-method")
def watchlist_remove_method(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    *,
    analysis: Annotated[
        str, typer.Option("--analysis", "-a", help="Method to remove every entry for, across every ticker.")
    ],
) -> None:
    """Remove every entry for the given method, across every ticker (bulk, idempotent)."""
    method = _parse_analysis(analysis)
    with _workspace_database() as database:
        repository = _watchlist_repository(database)
        try:
            removed = repository.remove_entries_for_method(name, _method_id_for_alias(method))
        except WatchlistNotFoundError as exc:
            _fail_with(exc)
        watchlist = _read_back_after_removal(repository, name, _removal_confirmation(removed, name, method))
    typer.echo(_watchlist_text(watchlist))


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
    if not yes and not _stdin_is_interactive():
        raise typer.BadParameter("--yes is required when input is not interactive.", param_hint="--yes")
    deleted: DeletedWatchlist | None = None
    with _workspace_database(json_output=json_output) as database:
        repository = _watchlist_repository(database)
        try:
            if not yes:
                summary = repository.summary(name)
                question = (
                    f"Delete watchlist {summary.display_name!r} (ID {summary.watchlist_id}, "
                    f"{_plural_entries(summary.entry_count)})? Saved Analysis Runs are kept."
                )
                if not typer.confirm(question):
                    typer.echo("Nothing was deleted.")
                    raise typer.Exit(code=1)
            deleted = repository.delete(name)
        except WatchlistNotFoundError as exc:
            if not missing_ok:
                _fail_with(exc, json_output=json_output)
    if deleted is None:
        if json_output:
            typer.echo(_document_json(WatchlistDeleteDocument(requested_name=name, deleted=False, watchlist=None)))
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
        _fail_with(deleted.unreadable, json_output=json_output)
    document = WatchlistDeleteDocument(
        requested_name=name, deleted=True, watchlist=_watchlist_document(deleted.watchlist)
    )
    typer.echo(_document_json(document))


@watchlist_app.command("rename")
def watchlist_rename(
    name: Annotated[str, typer.Argument(help="Current watchlist name.")],
    new_name: Annotated[str, typer.Argument(help="New display name.")],
    *,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the renamed watchlist document.")] = False,
) -> None:
    """Rename a watchlist. Saved Analysis Runs keep the name it had when they ran."""
    with _workspace_database(json_output=json_output) as database:
        repository = _watchlist_repository(database)
        try:
            repository.rename(name, new_name)
        except (WatchlistNotFoundError, WatchlistConflictError) as exc:
            _fail_with(exc, json_output=json_output)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        confirmation = f"Renamed watchlist {name!r} to {new_name.strip()!r}."
        if not json_output:
            typer.echo(confirmation)
        try:
            watchlist = repository.get(new_name)
        except StoredSelectionError as exc:
            if json_output:
                typer.echo(confirmation, err=True)
            _fail_with(exc, json_output=json_output)
    if watchlist is None:
        _fail(
            FailureReasonCode.WATCHLIST_NOT_FOUND, f"No watchlist named {new_name!r} exists.", json_output=json_output
        )
    typer.echo(_watchlist_json(watchlist) if json_output else _watchlist_text(watchlist))


@watchlist_app.command("list")
def watchlist_list() -> None:
    """List every watchlist with its entry count."""
    with _workspace_database() as database:
        summaries = _watchlist_repository(database).list()
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
    if normalized_group_by not in ("ticker", "method"):
        raise typer.BadParameter("--group-by must be 'ticker' or 'method'.")
    with _workspace_database(json_output=json_output) as database:
        watchlist = _watchlist_repository(database).get(name)
    if watchlist is None:
        _fail(FailureReasonCode.WATCHLIST_NOT_FOUND, f"No watchlist named {name!r} exists.", json_output=json_output)
    typer.echo(_watchlist_json(watchlist) if json_output else _watchlist_text(watchlist, group_by=normalized_group_by))


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
    json_output: Annotated[bool, typer.Option("--json", help="Emit one JSON array of summaries.")] = False,
) -> None:
    """List Analysis Run summaries, most recently completed first."""
    try:
        query = RunQuery(
            ticker=None if ticker is None else normalize_ticker(ticker),
            method_id=None if analysis is None else _method_id_for_alias(_parse_analysis(analysis)),
            status=None if status is None else _parse_status(status),
            refresh_id=None if refresh_id is None else _parse_run_id(refresh_id, field="--refresh-id"),
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    with _workspace_database(json_output=json_output) as database:
        summaries = SQLiteAnalysisRunRepository(database).list(query)
    if json_output:
        runs = RunsListDocument(
            tuple(
                RunSummaryDocument(
                    analysis_run_id=item.analysis_run_id,
                    ticker=item.ticker,
                    method_id=item.method_id,
                    status=item.status,
                    completed_at=item.completed_at,
                    refresh_id=item.refresh_id,
                )
                for item in summaries
            )
        )
        typer.echo(_document_json(runs))
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
    selected_count = sum((details, diagnostics, json_output))
    if selected_count > 1:
        raise typer.BadParameter("Choose only one of --details, --diagnostics, or --json.")
    parsed_id = _parse_run_id(run_id, field="RUN_ID")
    mode = (
        PresentationMode.JSON
        if json_output
        else PresentationMode.DIAGNOSTICS
        if diagnostics
        else PresentationMode.DETAILS
        if details
        else PresentationMode.CONCISE
    )
    with _workspace_database(json_output=json_output) as database:
        try:
            run = SQLiteAnalysisRunRepository(database).get(parsed_id)
        except ValueError as exc:
            # The repository's own documented contract: a malformed or internally
            # inconsistent stored envelope raises a plain ValueError from get().
            _fail(FailureReasonCode.INVALID_STORED_RUN, str(exc), json_output=json_output)
    if run is None:
        _fail(
            FailureReasonCode.ANALYSIS_RUN_NOT_FOUND,
            f"No Analysis Run with ID {parsed_id} exists.",
            json_output=json_output,
        )
    try:
        rendered = project_run(run, ReplayOptions(mode=mode), codecs=EVIDENCE_BY_KEY)
    except (UnsupportedProjectionError, UnsupportedRunVersionError, InvalidStoredRunError) as exc:
        _fail_with(exc, json_output=json_output)
    typer.echo(rendered)


def _parse_run_id(value: str, *, field: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise typer.BadParameter(
            f"{value!r} is not a valid Analysis Run ID. Use the full ID exactly as shown "
            "by 'runs list' or 'refresh' — not a shortened or partial value.",
            param_hint=field,
        ) from exc


def _parse_status(value: str) -> RunOutcome:
    try:
        return RunOutcome(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in RunOutcome)
        raise typer.BadParameter(f"--status must be one of: {allowed}.") from exc


def _run_summary_line(summary: AnalysisRunSummary) -> str:
    return (
        f"{summary.analysis_run_id}  {summary.ticker:<10} {_alias_for_method_id(summary.method_id):<24} "
        f"{summary.status.value:<14} {summary.completed_at.isoformat()}"
    )


def _refresh_executor(
    ticker: str, selection: AnalysisSelection, *, profile_cache: InstrumentProfileResolver
) -> ExecutionCapture:
    """Dispatch one (ticker, selection) job to its strategy's refresh executor.

    Each executor composes entirely fresh provider/resolver/cache dependencies
    per call — job-scoped, exactly as ``refresh_watchlist``'s own contract
    requires for safe concurrent use — mirroring precisely how each strategy's direct
    command (``src.strategies.<strategy>.cli``) composes the same dependencies for one invocation.
    The durable instrument-profile cache is the one exception: it is built
    once per refresh (over the refresh command's own database) and shared
    across concurrent jobs, exactly like the Analysis Run repository already
    is. ``CachedInstrumentProfileResolver`` serializes its own per-ticker
    critical section (P2-Profiles contract §13.6), so sharing it across
    worker threads is safe by the resolver's own contract, not by accident.
    A selection of a strategy with no CLI-tier entry raises
    ``UndeclaredStrategyError``; no strategy is a default.
    """
    return refresh_executor_for(selection)(ticker, selection, profile_cache=profile_cache)


def _refresh_has_failure(summary: RefreshSummary) -> bool:
    """True if any job failed to produce a result, or produced an unavailable/failed outcome."""
    for result in summary.results:
        if result.error is not None:
            return True
        status = result.run.status if result.run is not None else result.outcome
        if status in (RunOutcome.UNAVAILABLE, RunOutcome.FAILED):
            return True
    return False


def _refresh_text(summary: RefreshSummary) -> str:
    lines = [f"Refresh {summary.refresh_id} for {summary.watchlist_name!r}:"]
    for result in summary.results:
        method = _alias_for_method_id(result.method_id)
        if result.run is not None:
            lines.append(f"  {result.run.analysis_run_id}  {result.ticker:<10} {method:<24} {result.run.status.value}")
        elif result.outcome is not None:
            lines.append(f"  {'(not saved)':<38}{result.ticker:<10} {method:<24} {result.outcome.value}")
        else:
            lines.append(f"  {'':<38}{result.ticker:<10} {method:<24} error: {result.error}")
    counts = ", ".join(f"{key}={value}" for key, value in sorted(summary.counts.items()))
    lines.append(f"Counts: {counts}" if counts else "Counts: (none)")
    return "\n".join(lines)


def _refresh_result_document(result: RefreshJobResult) -> RefreshResultDocument:
    """Build one job's entry; its status is the saved run's, else the unsaved outcome's, else null."""
    status = result.run.status if result.run is not None else result.outcome
    return RefreshResultDocument(
        ticker=result.ticker,
        method_id=result.method_id,
        analysis_run_id=None if result.run is None else result.run.analysis_run_id,
        saved=result.run is not None,
        status=status,
        error=result.error,
        reason_code=None if result.reason_code is None else FailureReasonCode(result.reason_code),
    )


def _refresh_json(summary: RefreshSummary) -> str:
    """Emit the refresh summary document."""
    return _document_json(
        RefreshSummaryDocument(
            refresh_id=summary.refresh_id,
            watchlist_id=summary.watchlist_id,
            watchlist_name=summary.watchlist_name,
            results=tuple(_refresh_result_document(result) for result in summary.results),
            counts=summary.counts,
        )
    )


def refresh(
    name: Annotated[str, typer.Argument(help="Watchlist name to refresh.")],
    workers: Annotated[int, typer.Option("--workers", help="Concurrent job count, 1-4; defaults to 2.")] = 2,
    no_save: Annotated[
        bool,
        typer.Option("--no-save", help="Preview current numbers across the watchlist without saving any Analysis Run."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit one final JSON summary document.")] = False,
) -> None:
    """Execute every entry in a watchlist and, by default, persist each result.

    Nothing is printed until the refresh completes or is interrupted: no
    per-job progress chatter reaches stdout, only the final summary. A
    Ctrl+C during the refresh stops admitting new jobs, lets any job already
    running finish and persist normally, and exits 130 without a fabricated
    row for a job that never started. ``--no-save`` still runs every entry,
    but nothing is written to storage; each result is shown but has no
    Analysis Run ID to browse or replay afterward.
    """
    try:
        policy = RefreshPolicy(workers=workers)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    cancellation = threading.Event()
    previous_handler = signal.getsignal(signal.SIGINT)

    def _handle_sigint(signum: int, frame: object) -> None:
        del signum, frame
        cancellation.set()

    signal.signal(signal.SIGINT, _handle_sigint)
    try:
        with _workspace_database(json_output=json_output) as database:
            try:
                profile_cache = _production_instrument_profile_cache(database, clock=utc_now)
                summary = refresh_watchlist(
                    name,
                    watchlists=_watchlist_repository(database),
                    repository=SQLiteAnalysisRunRepository(database),
                    executor=lambda ticker, selection: _refresh_executor(
                        ticker, selection, profile_cache=profile_cache
                    ),
                    run_specs=RUN_SPECS_BY_KEY,
                    classify=lambda exception: classify_failure(exception).reason_code.value,
                    save=not no_save,
                    policy=policy,
                    cancellation=cancellation,
                )
            except WatchlistNotFoundError as exc:
                _fail_with(exc, json_output=json_output)
            except EmptyRefreshTargetError as exc:
                _fail_with(exc, json_output=json_output)
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    typer.echo(_refresh_json(summary) if json_output else _refresh_text(summary))

    if cancellation.is_set():
        raise typer.Exit(code=130)
    if _refresh_has_failure(summary):
        raise typer.Exit(code=1)


def register(app: typer.Typer) -> None:
    """Register the watchlist and runs sub-apps, and the refresh command, on the root Typer app."""
    app.add_typer(watchlist_app, name="watchlist")
    app.add_typer(runs_app, name="runs")
    app.command("refresh")(refresh)


__all__ = ["register", "runs_app", "settings", "watchlist_app"]
