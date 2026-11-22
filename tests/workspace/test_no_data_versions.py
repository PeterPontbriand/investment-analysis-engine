"""A run stored before a no-data failure became an unavailable input is refused by version, never misread."""

import pytest
from pydantic import ValidationError

from investment_analysis_engine.strategy_wiring import EVIDENCE_BY_KEY
from investment_analysis_engine.workspace.codecs import EvidenceCodec, UnsupportedRunVersionError, decode_evidence
from investment_analysis_engine.workspace.runs import PROJECTION_VERSION, RUN_SCHEMA_VERSION, AnalysisRun
from investment_analysis_engine.workspace_documents.refresh import RefreshSummaryDocument


@pytest.mark.parametrize("key", sorted(EVIDENCE_BY_KEY), ids=lambda key: key[0])
def test_a_stored_run_of_the_previous_result_version_is_refused_before_decoding(key: tuple[str, str]) -> None:
    codec: EvidenceCodec = EVIDENCE_BY_KEY[key]
    older = AnalysisRun.model_construct(
        analysis_id=key[0],
        method_id=key[1],
        ticker="KO",
        run_schema_version=RUN_SCHEMA_VERSION,
        projection_version=PROJECTION_VERSION,
        evidence_codec_version=codec.evidence_codec_version,
        config_schema_version=codec.config_schema_version,
        method_version=codec.method_version,
        result_schema_version=codec.result_schema_version - 1,
        result_evidence={"result": {}},
    )

    with pytest.raises(UnsupportedRunVersionError):
        decode_evidence(older, EVIDENCE_BY_KEY)


def test_a_refresh_summary_of_the_previous_version_is_refused() -> None:
    with pytest.raises(ValidationError):
        RefreshSummaryDocument.model_validate({"schema_version": 4})
