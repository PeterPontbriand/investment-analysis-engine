"""The Piotroski F-Score strategy's vocabulary.

It holds the identifiers and the stored-configuration version.

Like every strategy's vocabulary, this is a leaf: it imports nothing from its package.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal

AnalysisId = Literal["piotroski"]
MethodId = Literal["piotroski"]

ANALYSIS_ID: Final[AnalysisId] = "piotroski"
METHOD_ID: Final[MethodId] = "piotroski"

ConfigSchemaVersion = Literal[1]
CONFIG_SCHEMA_VERSION: Final[ConfigSchemaVersion] = 1

METHOD_VERSION: Final = 2
"""The version of the method's semantics: the nine tests, their operands, the score's rule and the anchor rule."""

RESULT_SCHEMA_VERSION: Final = 2
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


HEADLINE_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "score": "f-score",
        "completeness": "complete-and-partial-score",
    }
)
"""The glossary term that explains the label of each headline cell, by the cell's key."""

CODE_TERMS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "CheckOutcome": MappingProxyType(
            {
                CheckOutcome.PASS.value: "test-passed",
                CheckOutcome.FAIL.value: "test-failed",
                CheckOutcome.UNAVAILABLE.value: "unavailable-test",
            }
        ),
        "Completeness": MappingProxyType(
            {
                Completeness.COMPLETE.value: "score-complete",
                Completeness.PARTIAL.value: "score-partial",
            }
        ),
    }
)
"""The glossary term that explains each value of each code set this strategy defines, by the name of the OpenAPI
component that carries it."""
