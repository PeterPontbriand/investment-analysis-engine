"""Strict version-one codec for native FCF and earnings-growth evidence."""

import json

from pydantic import BaseModel, ConfigDict, model_validator

from src.analysis.strategy.fcf_earnings_growth.models import (
    METHOD_ID,
    METHOD_VERSION,
    SCHEMA_VERSION,
    STRATEGY_ID,
    FCFEarningsGrowthResult,
)
from src.workspace.models import StrictJsonMapping, _validate_json_value


class _FCFEvidence(BaseModel):
    """Fixed native result schema, independent of presentation and codec versions."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    result: FCFEarningsGrowthResult

    @model_validator(mode="after")
    def _validate_context(self) -> "_FCFEvidence":
        result = self.result
        if not result.ticker or result.ticker != result.ticker.strip().upper():
            raise ValueError("FCF evidence requires a normalized ticker.")
        for stamp in (result.requested_as_of, result.effective_as_of, result.period_start, result.period_end):
            if stamp is not None and stamp.utcoffset() is None:
                raise ValueError("FCF result timestamps must be timezone-aware.")
        for observation in result.annual_observations:
            if observation.period_start.utcoffset() is None or observation.period_end.utcoffset() is None:
                raise ValueError("Annual observation timestamps must be timezone-aware.")
        profile = result.instrument_profile
        if profile is not None:
            resolution = profile.security_unit_resolution
            if resolution is not None and resolution.provenance is not None:
                for document in resolution.provenance.documents:
                    if document.available_at.utcoffset() is None or document.retrieved_at.utcoffset() is None:
                        raise ValueError("Security-unit document timestamps must be timezone-aware.")
        return self


def encode_fcf_growth(evidence: FCFEarningsGrowthResult) -> StrictJsonMapping:
    """Capture a detached finite snapshot, revalidating native instances via JSON."""
    payload = _FCFEvidence(result=evidence).model_dump(mode="json")
    decode_fcf_growth(payload)
    return payload


def decode_fcf_growth(payload: StrictJsonMapping) -> FCFEarningsGrowthResult:
    """Restore declared native evidence without resolving inputs or computing metrics."""
    _validate_json_value(payload)
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("FCF result must be an object.")
    # Native init=False metadata is verified before constructor reconstruction.
    identifiers = {"strategy_id": STRATEGY_ID, "method_id": METHOD_ID}
    versions = {"method_version": METHOD_VERSION, "schema_version": SCHEMA_VERSION}
    if any(result.get(key) != value for key, value in identifiers.items()) or any(
        type(result.get(key)) is not int or result.get(key) != value for key, value in versions.items()
    ):
        raise ValueError("FCF native identifiers or versions do not match the declared evidence.")
    native = {key: value for key, value in result.items() if key not in identifiers and key not in versions}
    wire = {**payload, "result": native}
    return _FCFEvidence.model_validate_json(json.dumps(wire, allow_nan=False)).result
