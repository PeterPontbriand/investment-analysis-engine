"""The specimen's CLI-tier entry and the closed CLI tier the conformance tests build with it."""

from typing import Final

from investment_analysis_engine.cli_strategy_wiring import CLI_STRATEGIES, CliStrategy
from tests.specimen.cli import SELECTION_OPTIONS, add_selection, command
from tests.specimen.wiring import SPECIMEN_BEHAVIOR

SPECIMEN_CLI: Final = CliStrategy(
    behavior=SPECIMEN_BEHAVIOR,
    command=command,
    add_selection=add_selection,
    selection_options=SELECTION_OPTIONS,
)

SPECIMEN_CLI_STRATEGIES: Final = (*CLI_STRATEGIES, SPECIMEN_CLI)
