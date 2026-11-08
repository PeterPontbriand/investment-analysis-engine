"""Graham Growth's vocabulary: its names, its stored-configuration version and its shared enumerations.

This is the lowest-ranked role file of the strategy and imports nothing from it, so the selection class, the
analyzer modules, the document envelope and the composition root all read one declaration. Nothing else here is shared.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

AnalysisId = Literal["graham_growth_value"]
MethodId = Literal["graham_growth_value"]

ANALYSIS_ID: Final[AnalysisId] = "graham_growth_value"
METHOD_ID: Final[MethodId] = "graham_growth_value"

ConfigSchemaVersion = Literal[2]
CONFIG_SCHEMA_VERSION: Final[ConfigSchemaVersion] = 2


HEADLINE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "intrinsic_value": "intrinsic-value",
        "margin_of_safety": "margin-of-safety",
    }
)
"""The glossary term that explains the label of each headline cell, by the cell's key."""

CODE_TERMS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "GrahamGrowthSelectionEPSBasis": MappingProxyType(
            {
                "three_year_average": "eps-basis",
                "fiscal_year": "eps-basis",
            }
        ),
        "GrahamGrowthSelection.GrahamGrowthSelectionEPSBasis": MappingProxyType(
            {
                "three_year_average": "eps-basis",
                "fiscal_year": "eps-basis",
            }
        ),
    }
)
"""The glossary term that explains each value of each code set this strategy defines, by the name of the OpenAPI
component that carries it."""
