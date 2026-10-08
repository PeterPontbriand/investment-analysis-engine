"""Replay code the two Graham strategies share."""

from dataclasses import replace

from src.core.analysis_status import CalculationStatus
from src.reporting.evidence_presentation import friendly_valuation_failure
from src.strategies.graham_growth.calculation import GrowthValueInputAssembly
from src.strategies.graham_number.calculation import GrahamNumberInputAssembly

# Statuses whose stored `assembly.reason`/`result.reason` is already investor-facing
# (a successful calculation, or a method-level inapplicability message authored at
# the source); every other non-OK status carries a raw resolver reason that the live
# commands only ever show after `friendly_valuation_failure` normalizes it.
_REASON_ALREADY_SAFE = (CalculationStatus.OK, CalculationStatus.NOT_APPLICABLE)


def friendly_graham_assembly[AssemblyT: (GrahamNumberInputAssembly, GrowthValueInputAssembly)](
    ticker: str, assembly: AssemblyT
) -> AssemblyT:
    """Replace a genuine failure's raw reason with the live command's investor-facing text.

    Mirrors the Graham commands' failure output exactly: a successful or NOT_APPLICABLE assembly's reason is
    already safe to show verbatim (or, for OK, is None); any other status carries a raw resolver reason at
    capture time that the live command only ever displays after `friendly_valuation_failure` normalizes it.
    """
    if assembly.status in _REASON_ALREADY_SAFE:
        return assembly
    return replace(assembly, reason=friendly_valuation_failure(ticker, assembly.status, assembly.reason))
