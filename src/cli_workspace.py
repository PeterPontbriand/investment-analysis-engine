"""Watchlist, Analysis Run browsing, and refresh CLI: F1/F2/G3 of the local research workspace.

This module owns explicit Typer sub-apps and the bare ``refresh`` command; it
performs no storage or provider work at import time. Every command opens its
own short-lived, readiness-checked :class:`SQLiteDatabase`, borrows it for
one repository call, and closes it before returning — mirroring the existing
``_production_historical_client``/``_production_financial_cache`` pattern in
``src.cli_support``. Direct-command saving (``--save-run``) lives in
``src.cli``; this module's own provider/analyzer composition exists solely
to dispatch one refresh job per stored selection.
"""

import json
import signal
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Annotated, NoReturn
from uuid import UUID

import typer

from src.analysis.strategy.fcf_earnings_growth import (
    FCFClassificationBasis,
    FCFEarningsGrowthPolicy,
    ForwardPolicy,
    HistoricalHorizon,
    ProductionAnnualGrowthSeriesResolver,
)
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthInputResolver
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.analysis.strategy.momentum.momentum_analyzer import MomentumConfig
from src.cli_composition import build_graham_resolver, build_sec_production_provider, growth_assumptions
from src.cli_support import (
    _canonical_provider_id,
    _parse_as_of,
    _production_financial_cache,
    _production_historical_client,
    _production_instrument_profile_cache,
    config_usage_errors,
)
from src.config import settings
from src.data.financial.providers import SEC_PROVIDER_ID, YFINANCE_PROVIDER_ID
from src.data.instrument_profile import InstrumentProfileCandidate, compose_instrument_profile
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.readiness import DatabaseReadinessError, ensure_database_ready
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.repositories.watchlists import (
    SQLiteWatchlistRepository,
    WatchlistConflictError,
    WatchlistEntryNotFoundError,
    WatchlistNotFoundError,
)
from src.data.yfinance import YFinanceClient
from src.reporting.analysis_runs import ReplayOptions, UnsupportedProjectionError, project_run
from src.reporting.presentation import PresentationMode
from src.workspace.codecs import InvalidStoredRunError, UnsupportedRunVersionError
from src.workspace.execution import (
    ExecutionCapture,
    from_fcf_growth_capture,
    from_graham_growth_capture,
    from_graham_number_capture,
    from_momentum_capture,
)
from src.workspace.fcf_growth_execution import execute_fcf_growth
from src.workspace.graham_growth_execution import execute_graham_growth
from src.workspace.graham_number_execution import execute_graham_number
from src.workspace.models import RunOutcome
from src.workspace.momentum_execution import capture_momentum, run_momentum
from src.workspace.refresh import (
    EmptyRefreshTargetError,
    RefreshPolicy,
    RefreshSummary,
    refresh_watchlist,
)
from src.workspace.refresh import (
    WatchlistNotFoundError as RefreshWatchlistNotFoundError,
)
from src.workspace.requests import (
    AnalysisSelection,
    FCFGrowthSelection,
    FCFPolicySnapshot,
    GrahamGrowthSelection,
    GrahamNumberSelection,
    MomentumSelection,
)
from src.workspace.runs import AnalysisRunSummary, RunQuery, Watchlist, WatchlistEntry, WatchlistSummary
from src.workspace.watchlists import WatchlistSpec, normalize_ticker

watchlist_app = typer.Typer(help="Manage named watchlists of tickers and their analysis selections.")
runs_app = typer.Typer(help="Browse persisted Analysis Run history.")

_MOMENTUM_CLI_DEFAULTS = MomentumConfig()

# Amendment A1 (§12) keeps the existing hyphenated `--analysis` alias vocabulary
# used by watchlist commands; the mismatch with `runs list --method`'s canonical
# `method_id` values is a separately flagged, out-of-scope inconsistency.
_ANALYSIS_ALIASES = ("momentum", "graham-number", "graham-growth", "fcf-growth")
_ALIAS_METHOD_IDS = {
    "momentum": "sma_crossover",
    "graham-number": "graham_number",
    "graham-growth": "graham_growth_value",
    "fcf-growth": "reported_fcf_eps_cagr",
}


@contextmanager
def _workspace_database() -> Iterator[SQLiteDatabase]:
    """Own one invocation's readiness-checked database connection.

    A readiness failure is reported as a sanitized message and exit 1 here,
    at the one place every command shares, rather than repeated per command.
    """
    database = SQLiteDatabase(settings)
    try:
        try:
            ensure_database_ready(database)
        except DatabaseReadinessError as exc:
            _fail(str(exc))
        yield database
    finally:
        database.close()


def _fail(message: str) -> NoReturn:
    """Report a sanitized storage/readiness/lookup error and exit 1."""
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


def _selection_detail_text(selection: AnalysisSelection) -> str:
    """Render a selection's distinguishing fields, excluding its own identifiers."""
    payload = selection.model_dump(mode="json")
    payload.pop("method_id", None)
    payload.pop("analysis_id", None)
    payload.pop("config_schema_version", None)
    return ", ".join(f"{key}={value}" for key, value in sorted(payload.items()))


def _selection_summary(selection: AnalysisSelection) -> str:
    """Render one selection's method identifier and distinguishing fields, compactly."""
    detail = _selection_detail_text(selection)
    return f"{selection.method_id}: {detail}" if detail else selection.method_id


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
        (lambda entry: entry.selection.method_id) if group_by == "method" else (lambda entry: entry.ticker)
    )
    groups: dict[str, list[tuple[int, WatchlistEntry]]] = {}
    for index, entry in enumerate(watchlist.entries, start=1):
        groups.setdefault(key_of(entry), []).append((index, entry))
    for key, members in groups.items():
        lines.append(f"  {key}:")
        lines.extend(f"    [{index}] {_entry_line(entry, group_by=group_by)}" for index, entry in members)
    return "\n".join(lines)


def _watchlist_json(watchlist: Watchlist) -> str:
    """Emit the flat, ordered entry list, each carrying the same 1-based index a user sees."""
    payload = {
        "watchlist_id": str(watchlist.watchlist_id),
        "display_name": watchlist.display_name,
        "created_at": watchlist.created_at.isoformat(),
        "updated_at": None if watchlist.updated_at is None else watchlist.updated_at.isoformat(),
        "entries": [
            {"index": index, "ticker": entry.ticker, "selection": entry.selection.model_dump(mode="json")}
            for index, entry in enumerate(watchlist.entries, start=1)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False)


def _summary_line(summary: WatchlistSummary) -> str:
    plural = "y" if summary.entry_count == 1 else "ies"
    return f"{summary.display_name} ({summary.watchlist_id}): {summary.entry_count} entr{plural}"


def _parse_analysis(value: str) -> str:
    """Normalize and validate a watchlist ``--analysis`` alias."""
    normalized = value.strip().lower()
    if normalized not in _ANALYSIS_ALIASES:
        allowed = ", ".join(_ANALYSIS_ALIASES)
        raise typer.BadParameter(f"--analysis must be one of: {allowed}.")
    return normalized


def _check_momentum_windows(short_window: int, long_window: int, rsi_period: int) -> None:
    """Reject invalid SMA/RSI periods exactly as the direct ``momentum`` command does."""
    if short_window <= 0:
        raise typer.BadParameter(
            f"short window must be positive (received {short_window}).", param_hint="--short-window"
        )
    if long_window <= 0:
        raise typer.BadParameter(f"long window must be positive (received {long_window}).", param_hint="--long-window")
    if rsi_period <= 0:
        raise typer.BadParameter(f"RSI period must be positive (received {rsi_period}).", param_hint="--rsi-period")
    if short_window >= long_window:
        raise typer.BadParameter(f"short window ({short_window}) must be smaller than long window ({long_window}).")


def _fcf_historical_horizon(growth_years: int | None) -> HistoricalHorizon:
    """Convert the optional CLI horizon to the typed strict/automatic policy."""
    if growth_years is None:
        return HistoricalHorizon.LONGEST_AVAILABLE
    mapping = {3: HistoricalHorizon.THREE_YEARS, 4: HistoricalHorizon.FOUR_YEARS, 5: HistoricalHorizon.FIVE_YEARS}
    try:
        return mapping[growth_years]
    except KeyError as exc:
        raise typer.BadParameter("--growth-years must be 3, 4, or 5.") from exc


def _fcf_forward_policy(value: str) -> ForwardPolicy:
    """Map the hyphenated investor-facing CLI value to the normative enum."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return ForwardPolicy(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--forward-policy must be display-only, confirmation, or hard-gate.") from exc


def _fcf_classification_basis(value: str) -> FCFClassificationBasis:
    """Map the investor-facing CLI value to the typed FCF basis policy."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return FCFClassificationBasis(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--classification-basis must be total-fcf or fcf-per-share.") from exc


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
    """Build one validated selection from watchlist CLI flags.

    Mirrors the matching direct command's own flags and validation exactly
    (Amendment A1, §12's "Creation"/"Editing" sections), so a watchlist entry
    behaves identically to running that method directly. Only the flags
    relevant to ``method`` are consulted; the rest are ignored. ``fcf-growth``
    always executes against SEC EDGAR regardless of ``--data-provider``,
    exactly as the direct ``fcf-growth`` command's own persisted selection
    does; the flag is still validated for a consistent error experience.
    """
    if method == "momentum":
        _check_momentum_windows(short_window, long_window, rsi_period)
        return MomentumSelection(short_window=short_window, long_window=long_window, rsi_period=rsi_period)

    boundary = _parse_as_of(as_of)
    if method in ("graham-number", "graham-growth"):
        provider_id = _canonical_provider_id(data_provider) or SEC_PROVIDER_ID
        base = {
            "security_provider_id": provider_id,
            "eps_basis": eps_basis,
            "eps_override": eps,
            "quote_override": current_price,
            "as_of": boundary,
            "use_cache": not no_cache,
        }
        with config_usage_errors():
            if method == "graham-number":
                return GrahamNumberSelection.model_validate({**base, "bvps_override": bvps})
            if expected_growth is None:
                raise typer.BadParameter("Required when --analysis is graham-growth.", param_hint="--expected-growth")
            if aaa_yield is None:
                raise typer.BadParameter("Required when --analysis is graham-growth.", param_hint="--aaa-yield")
            return GrahamGrowthSelection.model_validate(
                {**base, "expected_growth": expected_growth, "aaa_yield_override": aaa_yield}
            )

    _canonical_provider_id(data_provider)
    normalized_currency = currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise typer.BadParameter("--currency must be a three-letter ISO 4217 code.")
    policy = FCFEarningsGrowthPolicy(
        historical_horizon=_fcf_historical_horizon(growth_years),
        classification_basis=_fcf_classification_basis(classification_basis),
        forward_policy=_fcf_forward_policy(forward_policy),
    )
    return FCFGrowthSelection(
        policy=FCFPolicySnapshot.model_validate(policy),
        currency=normalized_currency,
        provider_id="sec_edgar",
        as_of=boundary,
        use_cache=not no_cache,
    )


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
        typer.Option("--analysis", "-a", help="Method to seed: momentum, graham-number, graham-growth, or fcf-growth."),
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
        str | None, typer.Option("--as-of", help="Point-in-time boundary (graham-number/graham-growth/fcf-growth).")
    ] = None,
    data_provider: Annotated[
        str | None,
        typer.Option("--data-provider", help="Security-fact provider override (graham-number/graham-growth)."),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache", help="Bypass resolved-input cache reads/writes (graham-number/graham-growth/fcf-growth)."
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
        repository = SQLiteWatchlistRepository(database)
        try:
            watchlist = repository.create(WatchlistSpec(display_name=name))
        except WatchlistConflictError as exc:
            _fail(str(exc))
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
        typer.Option("--analysis", "-a", help="Method: momentum, graham-number, graham-growth, or fcf-growth."),
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
        str | None, typer.Option("--as-of", help="Point-in-time boundary (graham-number/graham-growth/fcf-growth).")
    ] = None,
    data_provider: Annotated[
        str | None,
        typer.Option("--data-provider", help="Security-fact provider override (graham-number/graham-growth)."),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache", help="Bypass resolved-input cache reads/writes (graham-number/graham-growth/fcf-growth)."
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
        repository = SQLiteWatchlistRepository(database)
        try:
            watchlist = repository.add_entries(name, entries)
        except WatchlistNotFoundError as exc:
            _fail(str(exc))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    typer.echo(_watchlist_text(watchlist))


@watchlist_app.command("remove-entry")
def watchlist_remove_entry(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    index: Annotated[int, typer.Argument(help="1-based entry number, as shown by 'watchlist show'.")],
) -> None:
    """Remove exactly one entry by its displayed 1-based index (Amendment A1, §12)."""
    if index < 1:
        raise typer.BadParameter("INDEX must be 1 or greater.")
    with _workspace_database() as database:
        repository = SQLiteWatchlistRepository(database)
        try:
            watchlist = repository.remove_entry(name, index - 1)
        except WatchlistNotFoundError as exc:
            _fail(str(exc))
        except WatchlistEntryNotFoundError as exc:
            _fail(str(exc))
    typer.echo(_watchlist_text(watchlist))


@watchlist_app.command("remove")
def watchlist_remove(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to remove every entry for, across every method.")],
) -> None:
    """Remove every entry for the given ticker(s), across every method (bulk, idempotent)."""
    with _workspace_database() as database:
        repository = SQLiteWatchlistRepository(database)
        try:
            watchlist = repository.remove_entries_for_ticker(name, tickers)
        except WatchlistNotFoundError as exc:
            _fail(str(exc))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    typer.echo(_watchlist_text(watchlist))


@watchlist_app.command("disable")
def watchlist_disable(
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    *,
    analysis: Annotated[
        str, typer.Option("--analysis", "-a", help="Method to remove every entry for, across every ticker.")
    ],
) -> None:
    """Remove every entry for the given method, across every ticker (bulk, idempotent)."""
    method = _parse_analysis(analysis)
    with _workspace_database() as database:
        repository = SQLiteWatchlistRepository(database)
        try:
            watchlist = repository.remove_entries_for_method(name, _ALIAS_METHOD_IDS[method])
        except WatchlistNotFoundError as exc:
            _fail(str(exc))
    typer.echo(_watchlist_text(watchlist))


@watchlist_app.command("list")
def watchlist_list() -> None:
    """List every watchlist with its entry count."""
    with _workspace_database() as database:
        summaries = SQLiteWatchlistRepository(database).list()
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
    with _workspace_database() as database:
        watchlist = SQLiteWatchlistRepository(database).get(name)
    if watchlist is None:
        _fail(f"No watchlist named {name!r} exists.")
    typer.echo(_watchlist_json(watchlist) if json_output else _watchlist_text(watchlist, group_by=normalized_group_by))


@runs_app.command("list")
def runs_list(  # noqa: PLR0913
    *,
    ticker: Annotated[str | None, typer.Option("--ticker", help="Filter by exact normalized ticker.")] = None,
    method: Annotated[str | None, typer.Option("--method", help="Filter by canonical method identifier.")] = None,
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
            method_id=method,
            status=None if status is None else _parse_status(status),
            refresh_id=None if refresh_id is None else _parse_run_id(refresh_id, field="--refresh-id"),
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    with _workspace_database() as database:
        summaries = SQLiteAnalysisRunRepository(database).list(query)
    if json_output:
        payload = [item.model_dump(mode="json") for item in summaries]
        typer.echo(json.dumps(payload, ensure_ascii=False, allow_nan=False))
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
    with _workspace_database() as database:
        try:
            run = SQLiteAnalysisRunRepository(database).get(parsed_id)
        except ValueError as exc:
            # The repository's own documented contract: a malformed or internally
            # inconsistent stored envelope raises a plain ValueError from get().
            _fail(str(exc))
    if run is None:
        _fail(f"No Analysis Run with ID {parsed_id} exists.")
    try:
        rendered = project_run(run, ReplayOptions(mode=mode))
    except (UnsupportedProjectionError, UnsupportedRunVersionError, InvalidStoredRunError) as exc:
        _fail(str(exc))
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
        f"{summary.analysis_run_id}  {summary.ticker:<10} {summary.method_id:<24} "
        f"{summary.status.value:<14} {summary.completed_at.isoformat()}"
    )


def _execute_momentum(
    ticker: str, selection: MomentumSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    data_client = YFinanceClient()
    executed_at = datetime.now(UTC)
    with _production_historical_client(data_client) as historical_client:
        run = run_momentum(selection, ticker, historical_client, executed_at=executed_at)

    def _identity_candidate() -> InstrumentProfileCandidate:
        return InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, data_client)

    identity_candidates = (_identity_candidate(),)
    kind_candidate = _identity_candidate()
    profile = (
        profile_cache.resolve(
            run.metrics.ticker, identity_candidates=identity_candidates, kind_candidate=kind_candidate
        )
        if profile_cache is not None
        else compose_instrument_profile(
            run.metrics.ticker, identity_candidates=identity_candidates, kind_candidate=kind_candidate
        )
    )
    return from_momentum_capture(capture_momentum(run, profile))


def _execute_graham_number(
    ticker: str, selection: GrahamNumberSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    config = selection.to_graham_number_config()
    executed_at = datetime.now(UTC)
    with _production_financial_cache(enabled=selection.use_cache) as cache:
        resolver = build_graham_resolver(
            resolver_type=GrahamNumberInputResolver,
            data_provider=config.security_provider_id,
            cache=cache,
            clock=lambda: executed_at,
        )
        capture = execute_graham_number(
            resolver,
            ticker,
            config,
            YFinanceClient(),
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            profile_cache=profile_cache,
        )
    return from_graham_number_capture(capture)


def _execute_graham_growth(
    ticker: str, selection: GrahamGrowthSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    config = selection.to_graham_growth_config()
    policy = growth_assumptions()
    executed_at = datetime.now(UTC)
    with _production_financial_cache(enabled=selection.use_cache) as cache:
        resolver = build_graham_resolver(
            resolver_type=GrahamGrowthInputResolver,
            data_provider=config.security_provider_id,
            cache=cache,
            clock=lambda: executed_at,
        )
        capture = execute_graham_growth(
            resolver,
            ticker,
            config,
            policy,
            YFinanceClient(),
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            profile_cache=profile_cache,
        )
    return from_graham_growth_capture(capture)


def _execute_fcf_growth(
    ticker: str, selection: FCFGrowthSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    config = selection.to_fcf_config()
    executed_at = datetime.now(UTC)
    with _production_financial_cache(enabled=selection.use_cache) as cache:
        provider = build_sec_production_provider()
        resolver = ProductionAnnualGrowthSeriesResolver(provider, cache=cache, clock=lambda: executed_at)
        capture = execute_fcf_growth(
            resolver,
            ticker,
            config=config,
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            provider=provider,
            profile_cache=profile_cache,
        )
    return from_fcf_growth_capture(capture)


def _refresh_executor(
    ticker: str, selection: AnalysisSelection, *, profile_cache: InstrumentProfileResolver
) -> ExecutionCapture:
    """Dispatch one (ticker, selection) job to its method's production adapter.

    Each branch composes entirely fresh provider/resolver/cache dependencies
    per call — job-scoped, exactly as ``refresh_watchlist``'s own contract
    requires for safe concurrent use — mirroring precisely how each direct
    command in ``src.cli`` composes the same dependencies for one invocation.
    The durable instrument-profile cache is the one exception: it is built
    once per refresh (over the refresh command's own database) and shared
    across concurrent jobs, exactly like the Analysis Run repository already
    is. ``CachedInstrumentProfileResolver`` serializes its own per-ticker
    critical section (P2-Profiles contract §13.6), so sharing it across
    worker threads is safe by the resolver's own contract, not by accident.
    """
    if isinstance(selection, MomentumSelection):
        return _execute_momentum(ticker, selection, profile_cache=profile_cache)
    if isinstance(selection, GrahamNumberSelection):
        return _execute_graham_number(ticker, selection, profile_cache=profile_cache)
    if isinstance(selection, GrahamGrowthSelection):
        return _execute_graham_growth(ticker, selection, profile_cache=profile_cache)
    if isinstance(selection, FCFGrowthSelection):
        return _execute_fcf_growth(ticker, selection, profile_cache=profile_cache)
    raise AssertionError(f"Unhandled analysis selection type: {type(selection)!r}")  # pragma: no cover


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
        if result.run is not None:
            lines.append(
                f"  {result.run.analysis_run_id}  {result.ticker:<10} {result.method_id:<24} {result.run.status.value}"
            )
        elif result.outcome is not None:
            lines.append(f"  {'(not saved)':<38}{result.ticker:<10} {result.method_id:<24} {result.outcome.value}")
        else:
            lines.append(f"  {'':<38}{result.ticker:<10} {result.method_id:<24} error: {result.error}")
    counts = ", ".join(f"{key}={value}" for key, value in sorted(summary.counts.items()))
    lines.append(f"Counts: {counts}" if counts else "Counts: (none)")
    return "\n".join(lines)


def _refresh_json(summary: RefreshSummary) -> str:
    payload = {
        "refresh_id": str(summary.refresh_id),
        "watchlist_id": str(summary.watchlist_id),
        "watchlist_name": summary.watchlist_name,
        "results": [
            {
                "ticker": result.ticker,
                "method_id": result.method_id,
                "analysis_run_id": (str(result.run.analysis_run_id) if result.run is not None else None),
                "saved": result.run is not None,
                "status": (
                    result.run.status.value
                    if result.run is not None
                    else result.outcome.value
                    if result.outcome is not None
                    else None
                ),
                "error": result.error,
            }
            for result in summary.results
        ],
        "counts": summary.counts,
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False)


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
        with _workspace_database() as database:
            try:
                profile_cache = _production_instrument_profile_cache(database)
                summary = refresh_watchlist(
                    name,
                    watchlists=SQLiteWatchlistRepository(database),
                    repository=SQLiteAnalysisRunRepository(database),
                    executor=lambda ticker, selection: _refresh_executor(
                        ticker, selection, profile_cache=profile_cache
                    ),
                    save=not no_save,
                    policy=policy,
                    cancellation=cancellation,
                )
            except RefreshWatchlistNotFoundError as exc:
                _fail(str(exc))
            except EmptyRefreshTargetError as exc:
                raise typer.BadParameter(str(exc)) from exc
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
