"""The specimen's CLI-layer functions: the direct command and the watchlist ``add-selection`` command.

The specimen is not in the production registry, so it builds its selection from its model directly instead of through
``build_selection``; the option table is the same shape as a production strategy's.
"""

from typing import Annotated, Final

import typer

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.selections import as_of_boundary
from investment_analysis_engine.cli_support import (
    SelectionOption,
    add_selection_entries,
    cache_enabled,
    parse_as_of,
    presentation_mode,
)
from investment_analysis_engine.config import settings
from investment_analysis_engine.core.clock import utc_now
from tests.specimen.application import specimen_analyzer
from tests.specimen.closed_types import as_selection_member
from tests.specimen.presenter import render_specimen
from tests.specimen.runs import SPECIMEN_RUN_STORE, build_specimen_run
from tests.specimen.selection import SpecimenSelection
from tests.specimen.workspace import execute_specimen, from_specimen_capture

DEFAULT_VALUE: Final = 3.0
"""The input value a command uses when it is not given one."""

VALUE_OPTION = Annotated[float, typer.Option("--value", help="The value to scale")]
AS_OF_SPECIMEN_OPTION = Annotated[str | None, typer.Option("--as-of", help="Point-in-time boundary")]
NO_CACHE_OPTION = Annotated[bool, typer.Option("--no-cache", help="Bypass the cache")]

SELECTION_OPTIONS = (
    SelectionOption("value", "value", "--value"),
    SelectionOption("as_of", "as_of", "--as-of", parse_as_of),
    SelectionOption("no_cache", "use_cache", "--no-cache", cache_enabled),
)
"""The selection field each selection option sets: the specimen's one table of options and fields."""


def _selection(*, value: float, as_of: str | None, no_cache: bool) -> SpecimenSelection:
    """Build the specimen's selection from the selection options of either command."""
    return SpecimenSelection(value=value, as_of=as_of_boundary(parse_as_of(as_of)), use_cache=cache_enabled(no_cache))


def command(  # noqa: PLR0913
    ticker: Annotated[str, typer.Argument(help="Target ticker symbol")],
    *,
    value: VALUE_OPTION = DEFAULT_VALUE,
    as_of: AS_OF_SPECIMEN_OPTION = None,
    no_cache: NO_CACHE_OPTION = False,
    details: Annotated[bool, typer.Option("--details", help="Show the inputs")] = False,
    diagnostics: Annotated[bool, typer.Option("--diagnostics", help="Show the effective time")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit stable machine-readable JSON")] = False,
    save_run: Annotated[bool, typer.Option("--save-run", help="Persist this attempt as a specimen run")] = False,
) -> None:
    """Scale a value by the specimen's configured multiplier."""
    mode = presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    selection = _selection(value=value, as_of=as_of, no_cache=no_cache)
    analyzer = specimen_analyzer(ApplicationContext(settings=settings))
    capture = execute_specimen(analyzer, ticker, selection, executed_at=utc_now())
    if save_run:
        SPECIMEN_RUN_STORE.insert(build_specimen_run(ticker, selection, from_specimen_capture(capture)))
    typer.echo(render_specimen(capture.result, mode))


def add_selection(  # noqa: PLR0913
    name: Annotated[str, typer.Argument(help="Watchlist name.")],
    tickers: Annotated[list[str], typer.Argument(help="Tickers to add this selection for.")],
    *,
    value: VALUE_OPTION = DEFAULT_VALUE,
    as_of: AS_OF_SPECIMEN_OPTION = None,
    no_cache: NO_CACHE_OPTION = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the updated watchlist document.")] = False,
) -> None:
    """Add one Specimen entry per ticker to an existing watchlist."""
    add_selection_entries(
        name,
        tickers,
        as_selection_member(_selection(value=value, as_of=as_of, no_cache=no_cache)),
        json_output=json_output,
    )
