"""Strict JSON evidence for the retained Momentum result and input context.

The fixed typed schema reconstructs only Momentum's declared dataclasses and
enums. No class names, providers, calculators or presentation properties are
dispatched from stored data. Optional values and ordered evidence are retained.
"""

import json

from pydantic import BaseModel, ConfigDict, model_validator

from src.analysis.strategy.momentum.momentum_analyzer import MomentumRun
from src.workspace.models import StrictJsonMapping, _validate_json_value


class _MomentumEvidence(BaseModel):
    """Version-one wire shape, independent of the public presenter JSON."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    run: MomentumRun

    @model_validator(mode="after")
    def _validate_context(self) -> "_MomentumEvidence":
        run = self.run
        ticker = run.metrics.ticker
        if not ticker or ticker != ticker.strip().upper():
            raise ValueError("Momentum evidence requires a normalized ticker.")
        if run.metrics.timestamp.utcoffset() is None:
            raise ValueError("Momentum timestamp must be timezone-aware.")
        profile = run.instrument_profile
        if profile is not None:
            if profile.ticker != ticker:
                raise ValueError("Momentum profile ticker does not match metrics.")
            resolution = profile.security_unit_resolution
            if resolution is not None and resolution.provenance is not None:
                for document in resolution.provenance.documents:
                    if document.available_at.utcoffset() is None or document.retrieved_at.utcoffset() is None:
                        raise ValueError("Document timestamps must be timezone-aware.")
        return self


def encode_momentum(evidence: MomentumRun) -> StrictJsonMapping:
    """Encode and revalidate a detached finite JSON snapshot of Momentum evidence.

    Validation runs through JSON even for already-constructed dataclasses so
    invalid native instances cannot bypass field and nested invariant checks.
    """
    payload = _MomentumEvidence(run=evidence).model_dump(mode="json")
    decode_momentum(payload)
    return payload


def decode_momentum(payload: StrictJsonMapping) -> MomentumRun:
    """Restore typed evidence, rejecting corrupt fields without recalculation.

    JSON-mode strict validation admits ISO dates, enum values and JSON arrays
    for their declared types while rejecting coercion of numeric strings/bools,
    unknown fields, invalid enums and non-finite numbers at every depth.
    """
    _validate_json_value(payload)
    return _MomentumEvidence.model_validate_json(json.dumps(payload, allow_nan=False)).run
