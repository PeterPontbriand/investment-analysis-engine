"""The specimen's application-tier entry and the closed application tier the conformance tests build with it.

``ApplicationStrategy`` types its run function and refresh executor with the closed production selection union; the
specimen's selection is not in it, so the functions keep the exact-type guard that ``pair_application`` gives a
production entry.
"""

from datetime import datetime
from typing import Final

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.application.tier import APPLICATION_STRATEGIES, ApplicationStrategy
from investment_analysis_engine.core.strategy_errors import undeclared
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.workspace.capture import ExecutionCapture
from tests.specimen.application import refresh, run
from tests.specimen.selection import SpecimenSelection
from tests.specimen.wiring import SPECIMEN_BEHAVIOR


def _run(
    context: ApplicationContext,
    ticker: str,
    selection: object,
    /,
    *,
    executed_at: datetime,
    profile_cache: InstrumentProfileResolver | None,
) -> StrategyRun:
    """Run the specimen for a selection of exactly its class."""
    if not isinstance(selection, SpecimenSelection) or type(selection) is not SpecimenSelection:
        raise undeclared("selection type", type(selection))
    return run(context, ticker, selection, executed_at=executed_at, profile_cache=profile_cache)


def _refresh(
    context: ApplicationContext,
    ticker: str,
    selection: object,
    /,
    *,
    profile_cache: InstrumentProfileResolver | None,
) -> ExecutionCapture:
    """Execute one refresh job for a selection of exactly the specimen's class."""
    if not isinstance(selection, SpecimenSelection) or type(selection) is not SpecimenSelection:
        raise undeclared("selection type", type(selection))
    return refresh(context, ticker, selection, profile_cache=profile_cache)


SPECIMEN_APPLICATION: Final = ApplicationStrategy(behavior=SPECIMEN_BEHAVIOR, run=_run, refresh=_refresh)

SPECIMEN_APPLICATION_STRATEGIES: Final = (*APPLICATION_STRATEGIES, SPECIMEN_APPLICATION)
