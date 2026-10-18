"""The specimen's CLI-layer functions: the direct command, the watchlist selection builder and the refresh executor.

The settings path of the composition root is exercised here: the multiplier comes from the specimen's
``settings.toml``, overridden per key by the user's ``strategies/specimen-test.toml``.
"""

from typing import Final

import typer

from investment_analysis_engine.cli_support import _parse_as_of, _presentation_mode
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.config import settings
from investment_analysis_engine.config.strategy_settings import load_strategy_settings
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.workspace.capture import ExecutionCapture
from tests.specimen.analyzer import SpecimenAnalyzer
from tests.specimen.closed_types import as_native_evidence
from tests.specimen.execution import execute_specimen, from_specimen_capture
from tests.specimen.presenter import render_specimen
from tests.specimen.runs import SPECIMEN_RUN_STORE, build_specimen_run
from tests.specimen.selection import SpecimenSelection
from tests.specimen.settings import SpecimenSettings
from tests.specimen.vocabulary import ALIAS

WATCHLIST_VALUE: Final = 3.0
"""The input value a watchlist entry of the specimen uses; the watchlist commands have no flag for it."""


def specimen_settings() -> SpecimenSettings:
    """Return the specimen's validated settings, loaded once per process."""
    return load_strategy_settings(ALIAS, SpecimenSettings, settings.config_dir)


def _analyzer() -> SpecimenAnalyzer:
    """Compose the analyzer with the configured multiplier."""
    return SpecimenAnalyzer(multiplier=specimen_settings().multiplier)


def build_selection(flags: WatchlistFlags) -> SpecimenSelection:
    """Build one validated specimen selection from the watchlist flags it concerns: the boundary and the cache."""
    return SpecimenSelection(value=WATCHLIST_VALUE, as_of=_parse_as_of(flags.as_of), use_cache=not flags.no_cache)


def refresh(
    ticker: str, selection: SpecimenSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one specimen refresh job; the calculation reads no profile, so the cache is unused."""
    del profile_cache
    execution = from_specimen_capture(execute_specimen(_analyzer(), ticker, selection, executed_at=utc_now()))
    return ExecutionCapture(
        native_evidence=as_native_evidence(execution.native_evidence), profile=None, outcome=execution.outcome
    )


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
    mode = _presentation_mode(details=details, diagnostics=diagnostics, json_output=json_output)
    selection = SpecimenSelection(value=value, as_of=_parse_as_of(as_of), use_cache=not no_cache)
    capture = execute_specimen(_analyzer(), ticker, selection, executed_at=utc_now())
    if save_run:
        SPECIMEN_RUN_STORE.insert(build_specimen_run(ticker, selection, from_specimen_capture(capture)))
    typer.echo(render_specimen(capture.result, mode))
