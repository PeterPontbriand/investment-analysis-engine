"""The specimen's CLI-layer functions: the direct command and the watchlist selection builder."""

from typing import Final

import typer

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.cli_support import parse_as_of, presentation_mode
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.config import settings
from investment_analysis_engine.core.clock import utc_now
from tests.specimen.application import specimen_analyzer
from tests.specimen.presenter import render_specimen
from tests.specimen.runs import SPECIMEN_RUN_STORE, build_specimen_run
from tests.specimen.selection import SpecimenSelection
from tests.specimen.workspace import execute_specimen, from_specimen_capture

WATCHLIST_VALUE: Final = 3.0
"""The input value a watchlist entry of the specimen uses; the watchlist commands have no flag for it."""


def build_selection(flags: WatchlistFlags) -> SpecimenSelection:
    """Build one validated specimen selection from the watchlist flags it concerns: the boundary and the cache."""
    return SpecimenSelection(value=WATCHLIST_VALUE, as_of=parse_as_of(flags.as_of), use_cache=not flags.no_cache)


def command(  # noqa: PLR0913
    ticker: str = typer.Argument(..., help="Target ticker symbol"),
    *,
    value: float = typer.Option(WATCHLIST_VALUE, "--value", help="The value to scale"),
    as_of: str | None = typer.Option(None, "--as-of", help="Point-in-time boundary"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the cache"),
    details: bool = typer.Option(False, "--details", help="Show the inputs"),
    diagnostics: bool = typer.Option(False, "--diagnostics", help="Show the effective time"),
    json_output: bool = typer.Option(False, "--json", help="Emit stable machine-readable JSON"),
    save_run: bool = typer.Option(False, "--save-run", help="Persist this attempt as a specimen run"),
) -> None:
    """Scale a value by the specimen's configured multiplier."""
    mode = presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    selection = SpecimenSelection(value=value, as_of=parse_as_of(as_of), use_cache=not no_cache)
    analyzer = specimen_analyzer(ApplicationContext(settings=settings))
    capture = execute_specimen(analyzer, ticker, selection, executed_at=utc_now())
    if save_run:
        SPECIMEN_RUN_STORE.insert(build_specimen_run(ticker, selection, from_specimen_capture(capture)))
    typer.echo(render_specimen(capture.result, mode))
