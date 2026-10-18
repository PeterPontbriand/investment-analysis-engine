"""The specimen's CLI-tier entry and the closed CLI tier the conformance tests build with it.

``CliStrategy`` types its selection builder with the closed production selection union; the specimen's selection is
not in it, so the one cast below is the specimen's departure from that field's type. The refresh executor takes any
object and keeps the exact-type guard that ``pair_cli`` gives a production entry.
"""

from typing import Final, cast

from investment_analysis_engine.cli_strategy_wiring import CLI_STRATEGIES, CliStrategy
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.core.strategy_errors import undeclared
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.strategy_types import SelectionMember
from tests.specimen.cli import build_selection, command, refresh
from tests.specimen.selection import SpecimenSelection
from tests.specimen.wiring import SPECIMEN_BEHAVIOR


def _build(flags: WatchlistFlags, /) -> SelectionMember:
    """Build the specimen's selection from the watchlist flags."""
    return cast("SelectionMember", build_selection(flags))


def _refresh(ticker: str, selection: object, /, *, profile_cache: InstrumentProfileResolver) -> ExecutionCapture:
    """Execute one refresh job for a selection of exactly the specimen's class."""
    if not isinstance(selection, SpecimenSelection) or type(selection) is not SpecimenSelection:
        raise undeclared("selection type", type(selection))
    return refresh(ticker, selection, profile_cache=profile_cache)


SPECIMEN_CLI: Final = CliStrategy(
    behavior=SPECIMEN_BEHAVIOR,
    build=_build,
    refresh=_refresh,
    command=command,
)

SPECIMEN_CLI_STRATEGIES: Final = (*CLI_STRATEGIES, SPECIMEN_CLI)
