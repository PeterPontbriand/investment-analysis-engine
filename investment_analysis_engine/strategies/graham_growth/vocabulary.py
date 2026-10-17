"""Graham Growth's vocabulary: its names, its stored-configuration version and its shared enumerations.

This is the lowest-ranked role file of the strategy and imports nothing from it, so the selection class, the
analyzer modules, the document envelope and the composition root all read one declaration. Nothing else here is shared.
"""

from typing import Final, Literal

AnalysisId = Literal["graham_growth_value"]
MethodId = Literal["graham_growth_value"]

ANALYSIS_ID: Final[AnalysisId] = "graham_growth_value"
METHOD_ID: Final[MethodId] = "graham_growth_value"

ConfigSchemaVersion = Literal[1]
CONFIG_SCHEMA_VERSION: Final[ConfigSchemaVersion] = 1
