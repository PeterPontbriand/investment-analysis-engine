"""The specimen's reviewed case and its arguments.

A production ``Case`` names its tools with the closed production ``ToolName``, so the specimen's case is a plain
record of its own: an identifier and the tool arguments it dispatches.
"""

from dataclasses import dataclass
from typing import Final

from tests.specimen.tool import SpecimenToolArguments


@dataclass(frozen=True)
class SpecimenCase:
    """One reviewed specimen case: its identifier and the arguments the tool is called with."""

    case_id: str
    arguments: SpecimenToolArguments


SPECIMEN_ARGUMENTS: Final = SpecimenToolArguments(ticker="SPEC", value=3.0)
"""The reviewed arguments: 3.0 scaled by the fixture composition's multiplier of 2.0 is 6.0."""

SPECIMEN_CASES: Final = (SpecimenCase(case_id="SPC-01", arguments=SPECIMEN_ARGUMENTS),)
