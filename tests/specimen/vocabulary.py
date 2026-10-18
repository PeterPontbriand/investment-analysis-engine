"""The specimen's vocabulary: its names and its stored-configuration version.

Like every strategy's vocabulary, this is a leaf: it imports nothing from its package.
"""

from typing import Final, Literal

AnalysisId = Literal["specimen"]
MethodId = Literal["specimen_method"]

ANALYSIS_ID: Final[AnalysisId] = "specimen"
METHOD_ID: Final[MethodId] = "specimen_method"
ALIAS: Final = "specimen-test"

ConfigSchemaVersion = Literal[1]
CONFIG_SCHEMA_VERSION: Final[ConfigSchemaVersion] = 1

METHOD_VERSION: Final = 1
RESULT_SCHEMA_VERSION: Final = 1
EVIDENCE_CODEC_VERSION: Final = 1
