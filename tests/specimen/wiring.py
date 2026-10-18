"""The specimen's descriptor and the closed tuple the conformance tests build with it.

The production ``STRATEGIES`` never names the specimen; ``SPECIMEN_STRATEGIES`` is built here, in test code. The
descriptor's ``tool`` field is typed with the closed production ``ToolName``, which the specimen's own tool
enumeration is not a member of, so the descriptor crosses it through :mod:`tests.specimen.closed_types`.
"""

from typing import Final

from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from tests.specimen.behavior import SpecimenBehavior
from tests.specimen.closed_types import as_tool_name
from tests.specimen.envelope import SpecimenDocument
from tests.specimen.settings import SpecimenSettings
from tests.specimen.tool import SpecimenTool, SpecimenToolArguments
from tests.specimen.vocabulary import (
    ALIAS,
    ANALYSIS_ID,
    CONFIG_SCHEMA_VERSION,
    EVIDENCE_CODEC_VERSION,
    METHOD_ID,
    METHOD_VERSION,
    RESULT_SCHEMA_VERSION,
)

SPECIMEN_BEHAVIOR: Final = SpecimenBehavior()

SPECIMEN: Final = StrategyDescriptor(
    analysis_id=ANALYSIS_ID,
    method_id=METHOD_ID,
    alias=ALIAS,
    label="Specimen",
    tool=as_tool_name(SpecimenTool.ANALYZE_SPECIMEN),
    tool_arguments=SpecimenToolArguments,
    tool_description="Scale a value by the specimen's configured multiplier.",
    behavior=SPECIMEN_BEHAVIOR,
    config_schema_version=CONFIG_SCHEMA_VERSION,
    method_version=METHOD_VERSION,
    result_schema_version=RESULT_SCHEMA_VERSION,
    evidence_codec_version=EVIDENCE_CODEC_VERSION,
    json_envelope=SpecimenDocument,
    settings_type=SpecimenSettings,
)

SPECIMEN_STRATEGIES: Final = (*STRATEGIES, SPECIMEN)
