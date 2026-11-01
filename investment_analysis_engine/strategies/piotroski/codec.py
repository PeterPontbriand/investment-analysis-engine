"""The Piotroski F-Score strategy's strict codec for its evidence."""

import json

from pydantic import BaseModel, ConfigDict, model_validator

from investment_analysis_engine.analysis.run_models import StrictJsonMapping, _validate_json_value
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiResult
from investment_analysis_engine.strategies.piotroski.vocabulary import (
    ANALYSIS_ID,
    METHOD_ID,
    METHOD_VERSION,
    RESULT_SCHEMA_VERSION,
)


class _PiotroskiEvidence(BaseModel):
    """Fixed native result schema, independent of presentation and codec versions."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    result: PiotroskiResult

    @model_validator(mode="after")
    def _validate_context(self) -> "_PiotroskiEvidence":
        result = self.result
        if not result.ticker or result.ticker != result.ticker.strip().upper():
            raise ValueError("Piotroski evidence requires a normalized ticker.")
        for stamp in (result.requested_as_of, result.effective_as_of):
            if stamp is not None and stamp.utcoffset() is None:
                raise ValueError("Piotroski result timestamps must be timezone-aware.")
        return self


def encode_piotroski(evidence: PiotroskiResult) -> StrictJsonMapping:
    """Capture a detached finite JSON snapshot of ``evidence``, revalidating it by decoding the snapshot."""
    payload = _PiotroskiEvidence(result=evidence).model_dump(mode="json")
    decode_piotroski(payload)
    return payload


def decode_piotroski(payload: StrictJsonMapping) -> PiotroskiResult:
    """Reconstruct the evidence without any calculation, rejecting an unknown, missing or ill-typed key."""
    _validate_json_value(payload)
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("Piotroski result must be an object.")
    # Native init=False metadata is verified before constructor reconstruction.
    identifiers = {"strategy_id": ANALYSIS_ID, "method_id": METHOD_ID}
    versions = {"method_version": METHOD_VERSION, "schema_version": RESULT_SCHEMA_VERSION}
    if any(result.get(key) != value for key, value in identifiers.items()) or any(
        type(result.get(key)) is not int or result.get(key) != value for key, value in versions.items()
    ):
        raise ValueError("Piotroski native identifiers or versions do not match the declared evidence.")
    native = {key: value for key, value in result.items() if key not in identifiers and key not in versions}
    wire = {**payload, "result": native}
    return _PiotroskiEvidence.model_validate_json(json.dumps(wire, allow_nan=False, ensure_ascii=False)).result


def piotroski_native_status(result: PiotroskiResult, /) -> CalculationStatus:
    """Return the status the strategy reports; the shared rule maps it to an outcome."""
    return result.execution_status


def piotroski_ticker(result: PiotroskiResult, /) -> str:
    """Return the ticker the evidence is about, which must equal its run envelope's ticker."""
    return result.ticker
