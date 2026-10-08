"""Graham Number's vocabulary: the identifiers and enumerations more than one of its files needs.

This is the lowest-ranked role file of the strategy and imports nothing from it, so the selection class, the
analyzer modules, the document envelope and the composition root all read one declaration. Nothing else here is shared.
"""

from typing import Final, Literal

AnalysisId = Literal["graham_number"]
MethodId = Literal["graham_number"]

ANALYSIS_ID: Final[AnalysisId] = "graham_number"
METHOD_ID: Final[MethodId] = "graham_number"
