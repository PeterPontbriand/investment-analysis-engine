"""The specimen's CLI-tier entry and the closed CLI tier the conformance tests build with it.

``CliStrategy`` types its selection builder with the closed production selection union; the specimen's selection is
not in it, so the builder crosses it through :mod:`tests.specimen.closed_types`.
"""

from typing import Final

from investment_analysis_engine.cli_strategy_wiring import CLI_STRATEGIES, CliStrategy
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.workspace.strategy_types import SelectionMember
from tests.specimen.cli import build_selection, command
from tests.specimen.closed_types import as_selection_member
from tests.specimen.wiring import SPECIMEN_BEHAVIOR


def _build(flags: WatchlistFlags, /) -> SelectionMember:
    """Build the specimen's selection from the watchlist flags."""
    return as_selection_member(build_selection(flags))


SPECIMEN_CLI: Final = CliStrategy(
    behavior=SPECIMEN_BEHAVIOR,
    build=_build,
    command=command,
)

SPECIMEN_CLI_STRATEGIES: Final = (*CLI_STRATEGIES, SPECIMEN_CLI)
