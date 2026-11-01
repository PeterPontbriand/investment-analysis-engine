"""The Piotroski F-Score strategy's vocabulary.

It holds the identifiers and the stored-configuration version.

Like every strategy's vocabulary, this is a leaf: it imports nothing from its package.
"""

from enum import StrEnum
from typing import Final, Literal

AnalysisId = Literal["piotroski"]
MethodId = Literal["piotroski"]

ANALYSIS_ID: Final[AnalysisId] = "piotroski"
METHOD_ID: Final[MethodId] = "piotroski"

ConfigSchemaVersion = Literal[1]
CONFIG_SCHEMA_VERSION: Final[ConfigSchemaVersion] = 1

METHOD_VERSION: Final = 1
"""The version of the method's semantics: the nine tests, their operands and the score's rule."""

RESULT_SCHEMA_VERSION: Final = 1
"""The version of the stored result's shape."""


class CheckOutcome(StrEnum):
    """Outcome of one test. An unavailable test is never a fail."""

    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


class Completeness(StrEnum):
    """Whether a score rests on all nine tests or on six to eight."""

    COMPLETE = "complete"
    PARTIAL = "partial"
