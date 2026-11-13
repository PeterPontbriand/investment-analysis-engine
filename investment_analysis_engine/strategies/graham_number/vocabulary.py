"""Graham Number's vocabulary: its names, its stored-configuration version and its shared enumerations.

This is the lowest-ranked role file of the strategy and imports nothing from it, so the selection class, the
analyzer modules, the document envelope and the composition root all read one declaration. Nothing else here is shared.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

AnalysisId = Literal["graham_number"]
MethodId = Literal["graham_number"]

ANALYSIS_ID: Final[AnalysisId] = "graham_number"
METHOD_ID: Final[MethodId] = "graham_number"

ConfigSchemaVersion = Literal[4]
CONFIG_SCHEMA_VERSION: Final[ConfigSchemaVersion] = 4


HEADLINE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "maximum_indicated_price": "maximum-indicated-price",
        "margin_of_safety": "margin-of-safety",
    }
)
"""The glossary term that explains the label of each headline cell, by the cell's key."""

CODE_TERMS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType({})
"""This strategy defines no code set of its own."""
